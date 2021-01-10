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
from threading import Timer, Lock
from uuid import uuid4
from requests import HTTPError
from os.path import join, dirname
from ovos_utils.configuration import update_mycroft_config
from ovos_utils.skills import blacklist_skill
from ovos_local_backend.configuration import CONFIGURATION
from adapt.intent import IntentBuilder
from time import sleep
from mycroft.api import DeviceApi, is_paired, check_remote_pairing
from mycroft.identity import IdentityManager
from mycroft.messagebus.message import Message
from mycroft.skills.core import MycroftSkill, intent_handler
import mycroft.audio


class PairingSkill(MycroftSkill):

    poll_frequency = 5  # secs between checking server for activation

    def __init__(self):
        super(PairingSkill, self).__init__("PairingSkill")
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

        self.in_pairing = False
        # specific vendors can override this
        if "pairing_url" not in self.settings:
            self.settings["pairing_url"] = "home.mycroft.ai"
        if "color" not in self.settings:
            self.settings["color"] = "#FF0000"

        self.initial_stt = self.config_core["stt"]["module"]
        self.in_confirmation = False
        self.confirmation_counter = 0
        self.using_mock = self.config_core["server"]["url"] != "https://api.mycroft.ai"

    # startup
    def initialize(self):
        self.add_event("mycroft.not.paired", self.not_paired)
        self.gui.register_handler("mycroft.device.set.backend",
                                  self.handle_backend_select)
        self.nato_dict = self.translate_namedvalues('codes')

        # If the device isn't paired catch mycroft.ready to report
        # that the device is ready for use.
        # This assumes that the pairing skill is loaded as a priority skill
        # before the rest of the skills are loaded.
        if not is_paired():
            self.add_event("mycroft.ready", self.handle_mycroft_ready)

        # blacklist conflicting skills
        blacklist_skill("mycroft-pairing.mycroftai")

        self.make_active()  # to enable converse

    def not_paired(self, message):
        if not message.data.get('quiet', True):
            self.speak_dialog("pairing.not.paired")
        self.handle_pairing()

    def handle_mycroft_ready(self, message):
        """Catch info that skills are loaded and ready."""
        self.mycroft_ready = True
        self.gui.remove_page("loading.qml")
        self.gui.release()

    # voice events
    def converse(self, utterances, lang=None):
        if self.in_pairing and "pair my device" in utterances:
            # mycroft-core emits this, let's capture it because we are
            # handling pairing already
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
            self.handle_use_selene()
        elif check_remote_pairing(ignore_errors=True):
            # Already paired! Just tell user
            self.speak_dialog("already.paired")
        elif not self.data:
            self.gui.show_page("BackendSelect.qml",
                               override_idle=True,
                               override_animations=True)
            self.in_confirmation = True
            self.confirmation_loop()
        self.in_pairing = False
        self.change_to_default()  # reset STT

    # stt handling
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

    # backend selection
    def confirmation_loop(self):
        if not self.in_confirmation:
            return  # gui event selection

        answer = self.get_response("choose_backend", num_retries=0)
        if answer:
            self.log.info("ANSWER: " + answer)
            if self.voc_match(answer, "no_backend"):
                if self.ask_yesno("confirm", {"backend": "local"}) == "yes":
                    self.handle_use_mock()
                    return
            elif self.voc_match(answer, "backend"):
                if self.ask_yesno("confirm", {"backend": "mycroft"}) == "yes":
                    self.handle_use_selene()
                    return

            # user said something not accounted for
            self.speak_dialog("no_understand", wait=True)
            # reset confirmation loop and keep asking
            self.confirmation_counter = 0
            self.confirmation_loop()
            return
        if not self.in_confirmation:
            return  # gui event selection
        self.confirmation_counter += 1
        if self.confirmation_counter >= 5:
            # no user answer, assume pairing wanted
            # NOTE: it could be a STT failure
            self.speak_dialog("force_pairing")
            self.handle_use_selene()
            return
        # keep asking user
        sleep(2)  # it talks way too much without this delay
        self.confirmation_loop()

    def handle_backend_select(self, message):
        # GUI selection event
        backend = message.data["backend"]
        self.in_confirmation = False
        self.confirmation_counter = 0
        if backend == "local":
            self.handle_use_mock(message)
        else:
            self.handle_use_selene(message)

    def handle_use_selene(self, message=None):
        # selene selected
        self.speak_dialog("mycroft", wait=True)
        if self.using_mock:
            self.enable_selene()
            self.data = None
            # TODO restart

        self.gui.remove_page("BackendSelect.qml")
        self.confirmation_counter = 0
        if check_remote_pairing(ignore_errors=True):
            # Already paired! Just tell user
            self.speak_dialog("already.paired")
            self.in_pairing = False
        elif not self.data:
            # continue to normal pairing process
            self.kickoff_pairing()

    def handle_use_mock(self, message=None):
        # mock backend selected
        self.speak_dialog("local", wait=True)
        if not self.using_mock:
            self.enable_mock()
            # TODO restart

        self.confirmation_counter = 0
        picture = join(dirname(__file__), "ui", "no_backend.png")
        self.gui.remove_page("BackendSelect.qml")
        self.gui.show_image(picture,
                            override_idle=True,
                            override_animations=True)
        self.in_pairing = False
        self.data = None

    def enable_selene(self):
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
        self.gui.show_page("pairing_start.qml", override_animations=True)

    def show_pairing(self, code):
        self.gui.remove_page("pairing_start.qml")
        self.enclosure.deactivate_mouth_events()
        self.enclosure.mouth_text(code)
        self.gui["txtcolor"] = self.settings["color"]
        self.gui["backendurl"] = self.settings["pairing_url"]
        self.gui["code"] = code
        self.gui.show_page("pairing.qml", override_animations=True)

    def show_pairing_success(self):
        self.enclosure.activate_mouth_events()  # clears the display
        self.gui.remove_page("pairing.qml")
        self.gui["status"] = "Success"
        self.gui["label"] = "Device Paired"
        self.gui["bgColor"] = "#40DBB0"
        self.gui.show_page("status.qml", override_animations=True)
        # allow GUI to linger around for a bit
        sleep(5)
        self.gui.remove_page("status.qml")
        self.gui.show_page("loading.qml", override_animations=True)

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
