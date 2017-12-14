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
    def __init__(self):
        super(PairingSkill, self).__init__("PairingSkill")
        self.api = DeviceApi()
        self.data = None
        self.last_request = None
        self.state = str(uuid4())
        self.delay = 10  # poll time used in checking server for activation
        self.expiration = 72000  # 20 hours
        self.activator = None
        self.activator_lock = Lock()
        self.activator_cancelled = False
        self.counter_lock = Lock()
        self.count = 0  # Counter for when to repeat the code

        # TODO: Add translation support
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
        intent = IntentBuilder("PairingIntent") \
            .require("PairingKeyword").require("DeviceKeyword").build()
        self.register_intent(intent, self.handle_pairing)
        self.add_event("mycroft.not.paired", self.not_paired)

    def not_paired(self, message):
        self.speak_dialog("pairing.not.paired")
        self.handle_pairing()

    def handle_pairing(self, message=None):
        with self.counter_lock:
            self.counter = 0

        if self.is_paired():
            self.speak_dialog("pairing.paired")
        elif not self.data:
            # Prevent auto-update during the pairing process
            self.reload_skill = False

            self.last_request = time.time() + self.expiration
            try:
                self.data = self.api.get_code(self.state)
            except ConnectionError:
                self.speak_dialog('connection.error')
                self.emitter.emit(Message("mycroft.mic.unmute", None))
                return

            # Make sure code stays on display
            self.enclosure.deactivate_mouth_events()

            # wait_while_speaking() support is mycroft-core 0.8.16+
            try:
                # This will make sure the user is in 0.8.16+ before continuing
                mycroft.util.wait_while_speaking()

                self.speak_dialog("pairing.intro")

                # HACK this gives the Mark 1 time to scroll the address and
                # the user time to browse to the website.
                # TODO: mouth_text() really should take an optional parameter
                # to not scroll a second time.
                self.enclosure.mouth_text("home.mycroft.ai      ")
                time.sleep(7)
                mycroft.util.wait_while_speaking()
            except:
                pass

            if not self.activator:
                self.__create_activator()

    def on_activate(self):
        """
            Function used by Timer. Checks if user has activated the device
            on home.mycroft.ai and if not repeats the pairing code every
            60 second.
        """
        try:
            # wait for a signal from the backend that pairing is complete
            token = self.data.get("token")
            login = self.api.activate(self.state, token)

            # is_speaking() and stop_speaking() support is mycroft-core 0.8.16+
            try:
                if mycroft.util.is_speaking():
                    # Assume speaking is the pairing code.  Stop TTS
                    mycroft.util.stop_speaking()
            except:
                pass

            self.enclosure.activate_mouth_events()  # clears the display
            self.speak_dialog("pairing.paired")

            # wait_while_speaking() support is mycroft-core 0.8.16+
            try:
                mycroft.util.wait_while_speaking()
            except:
                pass

            IdentityManager.save(login)
            self.emitter.emit(Message("mycroft.paired", login))

            # Un-mute.  Would have been muted during onboarding for a new
            # unit, and not dangerous to do if pairing was started
            # independently.
            self.emitter.emit(Message("mycroft.mic.unmute", None))

            # Send signal to update configuration
            self.emitter.emit(Message("configuration.updated"))

            # Allow this skill to auto-update again
            self.reload_skill = True
        except:
            # speak pairing code every 60th second
            with self.counter_lock:
                if self.count == 0:
                    self.speak_code()
                self.count = (self.count + 1) % 6

            if self.last_request < time.time():
                self.data = None
                self.handle_pairing()
            else:
                self.__create_activator()

    def __create_activator(self):
        with self.activator_lock:
            if not self.activator_cancelled:
                self.activator = Timer(self.delay, self.on_activate)
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
