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
from threading import Timer
from uuid import uuid4

from adapt.intent import IntentBuilder
from mycroft.api import DeviceApi
from mycroft.identity import IdentityManager
from mycroft.messagebus.message import Message
from mycroft.skills.core import MycroftSkill


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
            self.enclosure.deactivate_mouth_events()
            self.enclosure.mouth_text(self.data.get("code"))
            self.speak_code()
            self.__create_activator()

    def on_activate(self):
        try:
            # wait for a signal from the backend that pairing is complete
            token = self.data.get("token")
            login = self.api.activate(self.state, token)
            if self.repeater:
                self.repeater.cancel()
                self.repeater = None
            self.enclosure.activate_mouth_events()
            self.speak_dialog("pairing.paired")
            IdentityManager.save(login)
            self.emitter.emit(Message("mycroft.paired", login))
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
            device = self.api.find()
        except:
            device = None
        return device is not None

    def speak_code(self):
        code = self.data.get("code")
        self.log.info("Pairing code: " + code)
        data = {"code": '. '.join(map(self.nato_dict.get, code))}
        self.speak_dialog("pairing.code", data)

        # repeat instructions/code every 60 seconds (start to start)
        self.repeater = Timer(60, self.speak_code)
        self.repeater.daemon = True
        self.repeater.start()

    def shutdown(self):
        super(PairingSkill, self).shutdown()
        if self.activator:
            self.activator.cancel()


def create_skill():
    return PairingSkill()
