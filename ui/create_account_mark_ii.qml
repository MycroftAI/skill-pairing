/*
 * Copyright 2018 by Aditya Mehra <aix.m@outlook.com>
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *    http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 *
 */
import QtQuick 2.4
import QtQuick.Controls 2.0
import QtQuick.Layouts 1.4

import Mycroft 1.0 as Mycroft

/* Define a screen requesting that a user create an account before pairing. */
Mycroft.Delegate {
    id: root
    leftPadding: 0
    rightPadding: 0
    bottomPadding: 0
    topPadding: 0
    property int gridUnit: Mycroft.Units.gridUnit

    Rectangle {
        id: background
        anchors.fill: parent
        color: "#22a7f0"

        PairingLabel {
            id: firstLine
            anchors.top: parent.top
            anchors.topMargin: gridUnit * 3
            fontSize: 82
            fontStyle: "Bold"
            heightUnits: 4
            text: "Create a Mycroft"
        }

        PairingLabel {
            id: secondLine
            anchors.top: firstLine.bottom
            anchors.topMargin: gridUnit * 3
            fontSize: 82
            fontStyle: "Bold"
            heightUnits: 4
            text: "account"
        }

        PairingLabel {
            id: thirdLine
            anchors.top: secondLine.bottom
            anchors.topMargin: gridUnit * 2
            textColor: "#2C3E50"
            fontSize: 59
            fontStyle: "Bold"
            heightUnits: 3
            text: "account.mycroft.ai"
        }

        PairingLabel {
            id: fourthLine
            anchors.top: thirdLine.bottom
            anchors.topMargin: gridUnit * 2
            textColor: "#2C3E50"
            fontSize: 35
            fontStyle: "Regular"
            heightUnits: 2
            text: "pairing will begin shortly"
        }

        Rectangle {
            id: progressBarBackground
            anchors.bottom: parent.bottom
            anchors.bottomMargin: gridUnit * 2
            anchors.left: parent.left
            anchors.leftMargin: gridUnit * 2
            color: "#91D3F8"
            height: gridUnit * 2
            radius: 16
            width: gridUnit * 46
        }

        Rectangle {
            id: progressBarForeground
            anchors.bottom: parent.bottom
            anchors.bottomMargin: gridUnit * 2
            anchors.left: parent.left
            anchors.leftMargin: gridUnit * 2
            color: "#FD9E66"
            height: gridUnit * 2
            radius: 16

            NumberAnimation on width {
                id: progressBarAnimation
                to: gridUnit * 46
                duration: 30000
            }
        }
    }
}
