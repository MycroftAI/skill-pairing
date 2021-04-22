# Copyright 2017 Mycroft AI Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
import time
from time import sleep
from threading import Timer, Lock
from uuid import uuid4
from requests import HTTPError

from adapt.intent import IntentBuilder
from mycroft.api import DeviceApi, is_paired, check_remote_pairing
from mycroft.identity import IdentityManager
from mycroft.messagebus.message import Message
from mycroft.skills.core import intent_handler
from mycroft.util import create_daemon, connected
import mycroft.audio

from ovos_utils.configuration import update_mycroft_config
from ovos_utils.skills import blacklist_skill, make_priority_skill
from ovos_workshop.skills.decorators import killable_intent, killable_event
from ovos_workshop.skills import OVOSSkill
from ovos_local_backend.configuration import CONFIGURATION


class PairingSkill(OVOSSkill):
    poll_frequency = 5  # secs between checking server for activation

    def __init__(self):
        super(PairingSkill, self).__init__("PairingSkill")
        self.reload_skill = False
        self.api = DeviceApi()
        self.data = None
        self.time_code_expires = None
        self.state = str(uuid4())
        self.activator = None
        self.activator_lock = Lock()
        self.activator_cancelled = False

        self.counter_lock = Lock()
        self.count = -1  # for repeating pairing code. -1 = not running

        self.nato_dict = None
        self.mycroft_ready = False
        self.num_failed_codes = 0
        self.pairing_process_state = 0

        self.in_pairing = False
        # specific vendors can override this
        if "pairing_url" not in self.settings:
            self.settings["pairing_url"] = "home.mycroft.ai"
        if "color" not in self.settings:
            self.settings["color"] = "#FF0000"

        self.initial_stt = self.config_core["stt"]["module"]
        self.in_confirmation = False
        self.selection_done = False
        self.confirm_selection_done = False
        self.confirm_stt_selection_done = False
        self.confirmation_counter = 0
        self.using_mock = self.config_core["server"][
                              "url"] != "https://api.mycroft.ai"

    # startup
    def initialize(self):
        self.add_event("mycroft.not.paired", self.not_paired)
        self.add_event("mycroft.device.set.backend",
                       self.handle_backend_selected_event)
        self.add_event("mycroft.device.confirm.backend",
                       self.handle_backend_confirmation_event)
        self.add_event("mycroft.return.select.backend",
                       self.handle_return_event)
        self.add_event("mycroft.device.confirm.stt", self.select_stt)
        # duplicate events for GUI interaction
        self.gui.register_handler("mycroft.device.set.backend",
                                  self.handle_backend_selected_event)
        self.gui.register_handler("mycroft.device.confirm.backend",
                                  self.handle_backend_confirmation_event)
        self.gui.register_handler("mycroft.return.select.backend",
                                  self.handle_return_event)
        self.gui.register_handler("mycroft.device.confirm.stt",
                                  self.select_stt)
        self.nato_dict = self.translate_namedvalues('codes')

        paired = is_paired()

        if not paired:
            # If the device isn't paired catch mycroft.ready to report
            # that the device is ready for use.
            # This assumes that the pairing skill is loaded as a priority skill
            # before the rest of the skills are loaded.
            self.add_event("mycroft.ready", self.handle_mycroft_ready)

        # make priority skill if needed
        make_priority_skill(self.skill_id)
        # blacklist conflicting skill
        blacklist_skill("mycroft-pairing.mycroftai")

        self.make_active()  # to enable converse

        # show loading screen once wifi setup ends
        if not connected():
            self.bus.once("ovos.wifi.setup.completed", self.show_loading_screen)
        elif paired:
            # show loading screen right away
            # device has been paired and there is internet,
            # this is a priority skill which means mycroft is still loading
            # when this is called
            # NOTE this should be the first priority skill
            self.show_loading_screen()

    def show_loading_screen(self, message=None):
        self.gui.show_page("LoadingScreen.qml", override_animations=True)

    def send_stop_signal(self, stop_event=None, should_sleep=True):
        # stop the previous event execution
        if stop_event:
            self.bus.emit(Message(stop_event))
        # stop TTS
        self.bus.emit(Message("mycroft.audio.speech.stop"))
        if should_sleep:
            # STT might continue recording and screw up the next get_response
            # TODO make mycroft-core allow aborting recording in a sane way
            self.bus.emit(Message('mycroft.mic.mute'))
            sleep(0.5)  # if TTS had not yet started
            self.bus.emit(Message("mycroft.audio.speech.stop"))
            sleep(1.5)  # the silence from muting should make STT stop recording
            self.bus.emit(Message('mycroft.mic.unmute'))

    def handle_intent_aborted(self):
        self.log.info("killing all dialogs")

    def not_paired(self, message):
        if not message.data.get('quiet', True):
            self.speak_dialog("pairing.not.paired")
        self.handle_pairing()

    def handle_mycroft_ready(self, message):
        """Catch info that skills are loaded and ready."""
        self.mycroft_ready = True
        self.reload_skill = True
        self.gui.remove_page("InstallingSkills.qml")
        #don't do a full release because of bug with using self.gui.clear() in self.gui.release()
        #self.gui.release()
        #call mycroft.gui.screen.close directly over messagebus
        self.bus.emit(Message("mycroft.gui.screen.close",
                              {"skill_id": self.skill_id}))
        #Tell OVOS-GUI to finally collect resting screens
        self.bus.emit(Message("ovos.pairing.set.backend", {"backend": "mycroft"}))
        self.bus.emit(Message("ovos.pairing.process.completed"))

    # voice events
    def converse(self, utterances, lang=None):
        if self.in_pairing:
            # capture all utterances until paired
            # prompts from this skill are handled with get_response
            return True
        return False

    @intent_handler(IntentBuilder("PairingIntent")
                    .require("PairingKeyword").require("DeviceKeyword"))
    def handle_pairing(self, message=None):
        self.in_pairing = True

        if self.initial_stt == "mycroft":
            # STT not available, temporarily set chromium plugin
            self.change_to_plugin()

        if self.using_mock:
            # user triggered intent, wants to enable pairing
            self.select_selene()
        elif check_remote_pairing(ignore_errors=True):
            # Already paired! Just tell user
            self.speak_dialog("already.paired")
        elif not self.data:
            self.pairing_process_state = 1
            self.in_confirmation = True
            self.handle_backend_menu()

    # config handling
    def change_to_default(self):
        if self.initial_stt != "chromium_stt_plug":
            self.log.info("restoring STT configuration")
            config = {
                "stt": {
                    "module": self.initial_stt
                }
            }
            self.bus.emit(Message("configuration.patch", {"config": config}))

    def change_to_plugin(self):
        if self.initial_stt != "chromium_stt_plug":
            self.log.info("Temporarily setting chromium plugin (free STT)")
            config = {
                "stt": {
                    "module": "chromium_stt_plug"
                }
            }
            self.bus.emit(Message("configuration.patch", {"config": config}))
            time.sleep(5)  # allow STT to reload

    def change_to_kaldi(self):
        self.log.info("not implemented")

    def enable_selene(self):
        self.change_to_default()
        config = {
            "server": {
                "url": "https://api.mycroft.ai",
                "version": "v1"
            },
            "listener": {
                "wake_word_upload": {
                    "url": "https://training.mycroft.ai/precise/upload"
                }
            }
        }
        update_mycroft_config(config)
        self.using_mock = False
        self.bus.emit(Message("configuration.patch", {"config": config}))

    def enable_mock(self):
        url = "http://0.0.0.0:{p}".format(p=CONFIGURATION["backend_port"])
        version = CONFIGURATION["api_version"]
        config = {
            "server": {
                "url": url,
                "version": version
            },
            "listener": {
                "wake_word_upload": {
                    "url": "http://0.0.0.0:{p}/precise/upload".format(
                        p=CONFIGURATION["backend_port"])
                }
            }
        }
        update_mycroft_config(config)
        self.using_mock = True
        self.bus.emit(Message("configuration.patch", {"config": config}))

    # Pairing GUI events
    #### Backend selection menu
    @killable_event(msg="pairing.backend.menu.stop")
    def handle_backend_menu(self, wait=0):
        self.gui.show_page("BackendSelect.qml", override_idle=True,
                           override_animations=True)
        self.send_stop_signal("pairing.confirmation.stop")
        sleep(int(wait))
        self.speak_dialog("select_backend", wait=True)
        self.speak_dialog("backend", wait=True)
        sleep(1)
        answer = self.get_response("choose_backend", num_retries=0)
        if answer:
            self.log.info("ANSWER: " + answer)
            if self.voc_match(answer, "no_backend"):
                self.bus.emit(Message("mycroft.device.set.backend",
                                      {"backend": "local"}))
                return
            elif self.voc_match(answer, "backend"):
                self.bus.emit(Message("mycroft.device.set.backend",
                                      {"backend": "selene"}))
                return
            else:
                self.speak_dialog("no_understand", wait=True)

        sleep(1)  # time for abort to kick in
        # (answer will be None and return before this is killed)
        self.handle_backend_menu(wait=15)

    def handle_backend_selected_event(self, message):
        self.send_stop_signal("pairing.backend.menu.stop", should_sleep=False)
        self.in_confirmation = False
        self.confirmation_counter = 0
        self.selection_done = True
        self.pairing_process_state = 2
        self.handle_backend_confirmation(message.data["backend"])

    def handle_return_event(self, message):
        self.send_stop_signal("pairing.confirmation.stop", should_sleep=False)
        page = message.data["page"]
        self.in_confirmation = False
        self.selection_done = False
        self.confirmation_counter = 0
        if page == "selene":
            self.gui.remove_page("BackendMycroft.qml")
        else:
            self.gui.remove_page("BackendLocal.qml")
        self.handle_backend_menu()

    ### Backend confirmation
    @killable_event(msg="pairing.confirmation.stop",
                    callback=handle_intent_aborted)
    def handle_backend_confirmation(self, selection):
        self.log.info("SELECTED: " + selection)
        self.gui.remove_page("BackendSelect.qml")
        if selection == "local":
            self.gui.show_page("BackendLocal.qml", override_idle=True,
                               override_animations=True)
        else:
            self.gui.show_page("BackendMycroft.qml", override_idle=True,
                               override_animations=True)

        if selection == "selene":
            self.speak_dialog("selected_mycroft_backend", wait=True)
            # NOTE response might be None
            answer = self.ask_yesno("confirm_backend",
                                      {"backend": "mycroft"})
            if answer == "yes":
                self.bus.emit(Message("mycroft.device.confirm.backend",
                                      {"backend": "selene"}))
                return
            elif answer == "no":
                self.bus.emit(Message("mycroft.return.select.backend",
                                      {"page": "local"}))
                return
        elif selection == "local":
            self.speak_dialog("selected_local_backend", wait=True)
            # NOTE response might be None
            answer = self.ask_yesno("confirm_backend",
                                      {"backend": "local"})
            if answer == "yes":
                self.bus.emit(Message("mycroft.device.confirm.backend",
                                      {"backend": "local"}))
                return
            if answer == "no":
                self.bus.emit(Message("mycroft.return.select.backend",
                                      {"page": "selene"}))
                return
        sleep(5)  # time for abort to kick in
        # (answer will be None and return before this is killed)
        self.handle_backend_confirmation(selection)

    def handle_backend_confirmation_event(self, message):
        self.send_stop_signal("pairing.confirmation.stop")
        self.in_confirmation = False
        self.confirmation_counter = 0
        if message.data["backend"] == "local":
            self.select_local()
        else:
            self.select_selene()

    def select_selene(self):
        # selene selected

        self.gui.remove_page("BackendMycroft.qml")
        self.confirmation_counter = 0
        if self.using_mock:
            self.enable_selene()
            self.data = None
            # TODO needs to restart, user wants to change back to selene
            # eg, local was selected and at some point user said
            # "pair my device"

        if check_remote_pairing(ignore_errors=True):
            # Already paired! Just tell user
            self.speak_dialog("already.paired")
            self.in_pairing = False
        elif not self.data:
            # continue to normal pairing process
            self.kickoff_pairing()

    def select_local(self, message=None):
        # mock backend selected

        self.data = None
        self.handle_stt_menu()

    ### STT selection
    @killable_event(msg="pairing.stt.menu.stop",
                    callback=handle_intent_aborted)
    def handle_stt_menu(self):
        self.gui.remove_page("BackendLocal.qml")
        self.gui.show_page("BackendLocalConfig.qml", override_idle=True,
                           override_animations=True)
        self.send_stop_signal("pairing.confirmation.stop")

        self.speak_dialog("select_mycroft_stt")
        if self.ask_yesno("confirm_stt", {"stt": "google"}) == "yes":
            self.select_stt(selection="google")
        elif self.ask_yesno("confirm_stt", {"stt": "kaldi"}) == "yes":
            self.select_stt(selection="kaldi")
        else:
            self.speak_dialog("choice-failed")
            self.handle_stt_menu()

    def select_stt(self, selection=None):
        self.send_stop_signal("pairing.stt.menu.stop")
        if selection == "google":
            self.change_to_plugin()
        elif selection == "kaldi":
            self.change_to_kaldi()
        self.confirmation_counter = 0
        self.gui.remove_page("BackendLocalConfig.qml")
        self.gui.show_page("BackendLocalRestart.qml", override_idle=True,
                           override_animations=True)
        self.bus.emit(Message("ovos.pairing.set.backend", {"backend": "local"}))
        if not self.using_mock:
            self.enable_mock()
        # TODO restart
        self.in_pairing = False

    # pairing
    def kickoff_pairing(self):
        # Kick off pairing...
        with self.counter_lock:
            if self.count > -1:
                # We snuck in to this handler somehow while the pairing
                # process is still being setup.  Ignore it.
                self.log.debug("Ignoring call to handle_pairing")
                return
            # Not paired or already pairing, so start the process.
            self.count = 0
        self.reload_skill = False  # Prevent restart during the process

        self.log.debug("Kicking off pairing sequence")

        try:
            # Obtain a pairing code from the backend
            self.data = self.api.get_code(self.state)

            # Keep track of when the code was obtained.  The codes expire
            # after 20 hours.
            self.time_code_expires = time.monotonic() + 72000  # 20 hours
        except Exception:
            time.sleep(10)
            # Call restart pairing here
            # Bail out after Five minutes (5 * 6 attempts at 10 seconds
            # interval)
            if self.num_failed_codes < 5 * 6:
                self.num_failed_codes += 1
                self.abort_and_restart(quiet=True)
            else:
                self.end_pairing('connection.error')
                self.num_failed_codes = 0
            return

        self.num_failed_codes = 0  # Reset counter on success

        mycroft.audio.wait_while_speaking()

        self.show_pairing_start()
        self.speak_dialog("pairing.intro")

        # HACK this gives the Mark 1 time to scroll the address and
        # the user time to browse to the website.
        # TODO: mouth_text() really should take an optional parameter
        # to not scroll a second time.
        time.sleep(7)
        mycroft.audio.wait_while_speaking()

        if not self.activator:
            self.__create_activator()

    def check_for_activate(self):
        """Method is called every 10 seconds by Timer. Checks if user has
        activated the device yet on home.mycroft.ai and if not repeats
        the pairing code every 60 seconds.
        """
        try:
            # Attempt to activate.  If the user has completed pairing on the,
            # backend, this will succeed.  Otherwise it throws and HTTPError()

            token = self.data.get("token")
            login = self.api.activate(self.state, token)  # HTTPError() thrown

            # When we get here, the pairing code has been entered on the
            # backend and pairing can now be saved.
            # The following is kinda ugly, but it is really critical that we
            # get this saved successfully or we need to let the user know that
            # they have to perform pairing all over again at the website.
            try:
                IdentityManager.save(login)
            except Exception as e:
                self.log.debug("First save attempt failed: " + repr(e))
                time.sleep(2)
                try:
                    IdentityManager.save(login)
                except Exception as e2:
                    # Something must be seriously wrong
                    self.log.debug("Second save attempt failed: " + repr(e2))
                    self.abort_and_restart()

            if mycroft.audio.is_speaking():
                # Assume speaking is the pairing code.  Stop TTS of that.
                mycroft.audio.stop_speaking()

            self.show_pairing_success()
            self.bus.emit(Message("mycroft.paired", login))

            if self.mycroft_ready:
                # Tell user they are now paired
                self.speak_dialog("pairing.paired", wait=True)
            else:
                self.speak_dialog("wait.for.startup", wait=True)

            # Un-mute.  Would have been muted during onboarding for a new
            # unit, and not dangerous to do if pairing was started
            # independently.
            self.bus.emit(Message("mycroft.mic.unmute", None))

            # Send signal to update configuration
            self.bus.emit(Message("configuration.updated"))

            # Allow this skill to auto-update again
            self.reload_skill = True
        except HTTPError:
            # speak pairing code every 60th second
            with self.counter_lock:
                if self.count == 0:
                    self.speak_code()
                self.count = (self.count + 1) % 6

            if time.monotonic() > self.time_code_expires:
                # After 20 hours the token times out.  Restart
                # the pairing process.
                with self.counter_lock:
                    self.count = -1
                self.data = None
                self.handle_pairing()
            else:
                # trigger another check in 10 seconds
                self.__create_activator()
        except Exception as e:
            self.log.debug("Unexpected error: " + repr(e))
            self.abort_and_restart()

    def end_pairing(self, error_dialog):
        """Resets the pairing and don't restart it.

        Arguments:
            error_dialog: Reason for the ending of the pairing process.
        """
        self.speak_dialog(error_dialog)
        self.bus.emit(Message("mycroft.mic.unmute", None))

        self.data = None
        self.count = -1
        self.in_pairing = False

    def abort_and_restart(self, quiet=False):
        # restart pairing sequence
        self.log.debug("Aborting Pairing")
        self.enclosure.activate_mouth_events()
        if not quiet:
            self.speak_dialog("unexpected.error.restarting")

        # Reset state variables for a new pairing session
        with self.counter_lock:
            self.count = -1
        self.activator = None
        self.data = None  # Clear pairing code info
        self.log.info("Restarting pairing process")
        self.show_pairing_fail()
        self.bus.emit(Message("mycroft.not.paired",
                              data={'quiet': quiet}))

    def __create_activator(self):
        # Create a timer that will poll the backend in 10 seconds to see
        # if the user has completed the device registration process
        with self.activator_lock:
            if not self.activator_cancelled:
                self.activator = Timer(PairingSkill.poll_frequency,
                                       self.check_for_activate)
                self.activator.daemon = True
                self.activator.start()

    def speak_code(self):
        """Speak pairing code."""
        code = self.data.get("code")
        self.log.info("Pairing code: " + code)
        data = {"code": '. '.join(map(self.nato_dict.get, code)) + '.'}
        self.show_pairing(self.data.get("code"))
        self.speak_dialog("pairing.code", data)

    # GUI
    def show_pairing_start(self):
        # Make sure code stays on display
        self.enclosure.deactivate_mouth_events()
        self.enclosure.mouth_text(self.settings["pairing_url"] + "      ")
        self.gui.show_page("pairing_start.qml", override_idle=True,
                           override_animations=True)

    def show_pairing(self, code):
        self.gui.remove_page("pairing_start.qml")
        self.enclosure.deactivate_mouth_events()
        self.enclosure.mouth_text(code)
        self.gui["txtcolor"] = self.settings["color"]
        self.gui["backendurl"] = self.settings["pairing_url"]
        self.gui["code"] = code
        self.gui.show_page("pairing.qml", override_idle=True,
                           override_animations=True)

    def show_pairing_success(self):
        self.enclosure.activate_mouth_events()  # clears the display
        self.gui.remove_page("pairing.qml")
        self.gui["status"] = "Success"
        self.gui["label"] = "Device Paired"
        self.gui["bgColor"] = "#40DBB0"
        self.gui.show_page("status.qml", override_idle=True,
                           override_animations=True)
        # allow GUI to linger around for a bit
        sleep(5)
        self.gui.remove_page("status.qml")
        self.gui.show_page("InstallingSkills.qml", override_idle=True, override_animations=True)

    def show_pairing_fail(self):
        self.gui.release()
        self.gui["status"] = "Failed"
        self.gui["label"] = "Pairing Failed"
        self.gui["bgColor"] = "#FF0000"
        self.gui.show_page("status.qml", override_animations=True)
        sleep(5)
        self.gui.remove_page("status.qml")

    def shutdown(self):
        with self.activator_lock:
            self.activator_cancelled = True
            if self.activator:
                self.activator.cancel()
        if self.activator:
            self.activator.join()


def create_skill():
    return PairingSkill()
