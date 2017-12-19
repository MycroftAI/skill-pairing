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
from requests import ConnectionError

from adapt.intent import IntentBuilder
from mycroft.api import DeviceApi
from mycroft.identity import IdentityManager
from mycroft.messagebus.message import Message
from mycroft.skills.core import MycroftSkill
import mycroft.util


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

        # TODO:18.02 Add translation support
        # Can't change before then for fear of breaking really old mycroft-core
        # instances that just came up on wifi and haven't upgraded code yet.
        self.nato_dict = {'A': "'A' as in Apple", 'B': "'B' as in Bravo",
                          'C': "'C' as in Charlie", 'D': "'D' as in Delta",
                          'E': "'E' as in Echo", 'F': "'F' as in Fox trot",
                          'G': "'G' as in Golf", 'H': "'H' as in Hotel",
                          'I': "'I' as in India", 'J': "'J' as in Juliet",
                          'K': "'K' as in Kilogram", 'L': "'L' as in London",
                          'M': "'M' as in Mike", 'N': "'N' as in November",
                          'O': "'O' as in Oscar", 'P': "'P' as in Paul",
                          'Q': "'Q' as in Quebec", 'R': "'R' as in Romeo",
                          'S': "'S' as in Sierra", 'T': "'T' as in Tango",
                          'U': "'U' as in Uniform", 'V': "'V' as in Victor",
                          'W': "'W' as in Whiskey", 'X': "'X' as in X-Ray",
                          'Y': "'Y' as in Yankee", 'Z': "'Z' as in Zebra",
                          '1': 'One', '2': 'Two', '3': 'Three',
                          '4': 'Four', '5': 'Five', '6': 'Six',
                          '7': 'Seven', '8': 'Eight', '9': 'Nine',
                          '0': 'Zero'}

    def initialize(self):
        # TODO:18.02 - use decorator
        intent = IntentBuilder("PairingIntent") \
            .require("PairingKeyword").require("DeviceKeyword").build()
        self.register_intent(intent, self.handle_pairing)
        self.add_event("mycroft.not.paired", self.not_paired)

    def not_paired(self, message):
        self.speak_dialog("pairing.not.paired")
        self.handle_pairing()

    def handle_pairing(self, message=None):
        if self.is_paired():
            # Already paired!  Just tell user
            self.speak_dialog("pairing.paired")
        elif self.count > -1:
            # We snuck in to this handler somehow while the pairing process
            # is still being setup.  Ignore it.
            self.log.debug("Ignoring call to handle_pairing")
        elif not self.data:
            # Not paired or already pairing, so start the process.
            with self.counter_lock:
                self.count = 0
            self.reload_skill = False  # Prevent restart during the process

            self.log.debug("Kicking off pairing sequence")

            try:
                # Obtain a pairing code from the backend
                self.data = self.api.get_code(self.state)
                
                # Keep track of when the code was obtained.  The codes expire
                # after 20 hours.
                self.time_code_expires = time.time() + 72000  # 20 hours
            except ConnectionError:
                self.log.debug("Failed to get pairing code")
                self.speak_dialog('connection.error')
                self.emitter.emit(Message("mycroft.mic.unmute", None))
                return

            # wait_while_speaking() support is mycroft-core 0.8.16+
            try:
                # This will make sure the user is in 0.8.16+ before continuing
                # so a < 0.8.16 system will skip writing the URL to the mouth
                mycroft.util.wait_while_speaking()

                self.speak_dialog("pairing.intro")

                self.enclosure.deactivate_mouth_events()
                self.enclosure.mouth_text("home.mycroft.ai      ")
                # HACK this gives the Mark 1 time to scroll the address and
                # the user time to browse to the website.
                # TODO: mouth_text() really should take an optional parameter
                # to not scroll a second time.
                time.sleep(7)
                mycroft.util.wait_while_speaking()
            except:
                pass

            if not self.activator:
                self.__create_activator()

    def check_for_activate(self):
        """
            Function called ever 10 seconds by Timer. Checks if user has
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
            # The following is kinda ugly, but it is really critical that we get
            # this saved successfully or we need to let the user know that they
            # have to perform pairing all over again at the website.
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

            # is_speaking() and stop_speaking() support is mycroft-core 0.8.16+
            try:
                if mycroft.util.is_speaking():
                    # Assume speaking is the pairing code.  Stop TTS of that.
                    mycroft.util.stop_speaking()
            except:
                pass

            self.enclosure.activate_mouth_events()  # clears the display
            
            # Tell user they are now paired
            self.speak_dialog("pairing.paired")
            try:
                mycroft.util.wait_while_speaking()
            except:
                pass

            # Notify the system it is paired and ready
            self.emitter.emit(Message("mycroft.paired", login))

            # Un-mute.  Would have been muted during onboarding for a new
            # unit, and not dangerous to do if pairing was started
            # independently.
            self.emitter.emit(Message("mycroft.mic.unmute", None))

            # Send signal to update configuration
            self.emitter.emit(Message("configuration.updated"))

            # Allow this skill to auto-update again
            self.reload_skill = True
        except HTTPError:
            # speak pairing code every 60th second
            with self.counter_lock:
                if self.count == 0:
                    self.speak_code()
                self.count = (self.count + 1) % 6

            if time.time() > self.time_code_expires:
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
            
    def abort_and_restart(self):
        # restart pairing sequence
        self.enclosure.activate_mouth_events()
        self.speak_dialog("unexpected.error.restarting")
        self.emitter.emit(Message("mycroft.not.paired", login))
        self.count = -1
        self.activator = None


    def __create_activator(self):
        # Create a timer that will poll the backend in 10 seconds to see
        # if the user has completed the device registration process
        with self.activator_lock:
            if not self.activator_cancelled:
                self.activator = Timer(PairingSkill.poll_frequency,
                                       self.check_for_activate)
                self.activator.daemon = True
                self.activator.start()

    def is_paired(self):
        """ Determine if pairing process has completed. """
        try:
            device = self.api.get()
        except:
            device = None
        return device is not None

    def speak_code(self):
        """ Speak pairing code. """
        code = self.data.get("code")
        self.log.info("Pairing code: " + code)
        data = {"code": '. '.join(map(self.nato_dict.get, code))}
        
        # Make sure code stays on display
        self.enclosure.deactivate_mouth_events()
        self.enclosure.mouth_text(self.data.get("code"))
        self.speak_dialog("pairing.code", data)

    def shutdown(self):
        super(PairingSkill, self).shutdown()
        with self.activator_lock:
            self.activator_cancelled = True
            if self.activator:
                self.activator.cancel()
        if self.activator:
            self.activator.join()


def create_skill():
    return PairingSkill()
