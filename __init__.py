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

from adapt.intent import IntentBuilder

from mycroft.api import DeviceApi, is_paired, check_remote_pairing
from mycroft.identity import IdentityManager
from mycroft.messagebus.message import Message
from mycroft.skills.core import MycroftSkill, intent_handler
import mycroft.audio


PLATFORMS_WITH_BUTTON = ('mycroft_mark_1')


class PairingSkill(MycroftSkill):

    poll_frequency = 10  # secs between checking server for activation

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
        self.pair_dialog_lock = Lock()
        self.paired_dialog = 'pairing.paired'
        self.pairing_performed = False

        self.num_failed_codes = 0

    def initialize(self):
        self.add_event("mycroft.not.paired", self.not_paired)
        self.nato_dict = self.translate_namedvalues('codes')

        # If the device isn't paired catch mycroft.ready to report
        # that the device is ready for use.
        # This assumes that the pairing skill is loaded as a priority skill
        # before the rest of the skills are loaded.
        if not is_paired():
            self.add_event("mycroft.ready", self.handle_mycroft_ready)

        platform = self.config_core['enclosure'].get('platform', 'unknown')
        if platform in PLATFORMS_WITH_BUTTON:
            self.paired_dialog = 'pairing.paired'
        else:
            self.paired_dialog = 'pairing.paired.no.button'

    def handle_mycroft_ready(self, message):
        """Catch info that skills are loaded and ready."""
        with self.pair_dialog_lock:
            if is_paired() and self.pairing_performed:
                self.speak_dialog(self.paired_dialog)
            else:
                self.mycroft_ready = True

    def not_paired(self, message):
        if not message.data.get('quiet', True):
            self.speak_dialog("pairing.not.paired")
        self.handle_pairing()

    @intent_handler(IntentBuilder("PairingIntent")
                    .require("PairingKeyword").require("DeviceKeyword"))
    def handle_pairing(self, message=None):
        if check_remote_pairing(ignore_errors=True):
            # Already paired! Just tell user
            self.speak_dialog("already.paired")
        elif not self.data:
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

            self.gui.show_page("pairing_start.qml", override_idle=True)
            self.speak_dialog("pairing.intro")

            self.enclosure.deactivate_mouth_events()
            self.enclosure.mouth_text("home.mycroft.ai      ")
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

            self.enclosure.activate_mouth_events()  # clears the display

            # Notify the system it is paired
            self.gui.show_page("pairing_done.qml", override_idle=False)
            self.bus.emit(Message("mycroft.paired", login))

            self.pairing_performed = True
            with self.pair_dialog_lock:
                if self.mycroft_ready:
                    # Tell user they are now paired
                    self.speak_dialog(self.paired_dialog)
                    mycroft.audio.wait_while_speaking()
                else:
                    self.speak_dialog("wait.for.startup")
                    mycroft.audio.wait_while_speaking()

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

        # Make sure code stays on display
        self.enclosure.deactivate_mouth_events()
        self.enclosure.mouth_text(self.data.get("code"))
        self.gui['code'] = self.data.get("code")
        self.gui.show_page("pairing.qml", override_idle=True)
        self.speak_dialog("pairing.code", data)

    def shutdown(self):
        with self.activator_lock:
            self.activator_cancelled = True
            if self.activator:
                self.activator.cancel()
        if self.activator:
            self.activator.join()


def create_skill():
    return PairingSkill()
