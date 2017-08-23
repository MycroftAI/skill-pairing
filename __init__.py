# Copyright 2016 Mycroft AI, Inc.
#
# This file is part of Mycroft Core.
#
# Mycroft Core is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Mycroft Core is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Mycroft Core.  If not, see <http://www.gnu.org/licenses/>.

import time
from threading import Timer
from uuid import uuid4

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
        self.delay = 10
        self.expiration = 72000  # 20 hours
        self.activator = None
        self.repeater = None

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
        self.emitter.on("mycroft.not.paired", self.not_paired)

    def not_paired(self, message):
        self.speak_dialog("pairing.not.paired")
        self.handle_pairing()

    def handle_pairing(self, message=None):
        if self.is_paired():
            self.speak_dialog("pairing.paired")
        elif self.data and self.last_request < time.time():
            self.speak_code()
        else:
            self.last_request = time.time() + self.expiration
            self.data = self.api.get_code(self.state)
            self.enclosure.deactivate_mouth_events()  # keeps code on the display
            self.speak_code()
            if not self.activator:
                self.__create_activator()

    def on_activate(self):
        try:
            # wait for a signal from the backend that pairing is complete
            token = self.data.get("token")
            login = self.api.activate(self.state, token)

            # shut down thread that repeats the code to the user
            if self.repeater:
                self.repeater.cancel()
                self.repeater = None

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

        except:
            if self.last_request < time.time():
                self.data = None
                self.handle_pairing()
            else:
                self.__create_activator()

    def __create_activator(self):
        self.activator = Timer(self.delay, self.on_activate)
        self.activator.daemon = True
        self.activator.start()

    def is_paired(self):
        try:
            device = self.api.get()
        except:
            device = None
        return device is not None

    def speak_code(self):
        """ speak code and start repeating it every 60 second. """
        if self.repeater:
            self.repeater.cancel()
            self.repeater = None

        self.__speak_code()
        self.repeater = Timer(60, self.__repeat_code)
        self.repeater.daemon = True
        self.repeater.start()

    def __speak_code(self):
        """ Speak code. """
        code = self.data.get("code")
        self.log.info("Pairing code: " + code)
        data = {"code": '. '.join(map(self.nato_dict.get, code))}
        self.enclosure.mouth_text(self.data.get("code"))
        self.speak_dialog("pairing.code", data)

    def __repeat_code(self):
        """ Timer function to repeat the code every 60 second. """
        # if pairing is complete terminate the thread
        if self.is_paired():
            self.repeater = None
            return
        # repeat instructions/code every 60 seconds (start to start)
        self.__speak_code()
        self.repeater = Timer(60, self.__repeat_code)
        self.repeater.daemon = True
        self.repeater.start()

    def stop(self):
        pass

    def shutdown(self):
        super(PairingSkill, self).shutdown()
        if self.activator:
            self.activator.cancel()
        if self.repeater:
            self.repeater.cancel()


def create_skill():
    return PairingSkill()
