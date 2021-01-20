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

import QtQuick.Layouts 1.4
import QtQuick 2.4
import QtQuick.Controls 2.0
import org.kde.kirigami 2.4 as Kirigami

import Mycroft 1.0 as Mycroft

/* Screen to display the device pairing code to the user */
Mycroft.Delegate {
    id: root
    leftPadding: 0
    rightPadding: 0
    bottomPadding: 0
    topPadding: 0
    property var pairingCode: sessionData.code

    Rectangle {
        color: "#22a7f0"
        width: parent.width
        height: parent.height

        Item {
            anchors.fill: parent
            anchors.margins: Kirigami.Units.largeSpacing

            Text {
                id: pairingCode
                anchors.bottom: screenCenter.top
                width: parent.width
                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.WordWrap
                elide: Text.ElideRight
                font.family: "Noto Sans"
                font.weight: Font.ExtraBold
                fontSizeMode: Text.HorizontalFit
                minimumPixelSize: 65
                font.pixelSize: Math.max(root.height * 0.25, minimumPixelSize)
                color: "white"
                text: root.pairingCode
            }

            Item {
                id: screenCenter
                anchors.centerIn: parent
                height: 1
                width: parent.width
            }

            Item {
                id: pairAtItem
                anchors.top: screenCenter.bottom
                anchors.left: parent.left
                anchors.topMargin: 24
                width: parent.width / 3
                height: pairAtText.paintedHeight

                Text {
                    id: pairAtText
                    width: parent.width
                    horizontalAlignment: Text.AlignRight
                    verticalAlignment: Text.AlignVCenter
                    wrapMode: Text.WordWrap
                    elide: Text.ElideRight
                    font.family: "Noto Sans"
                    font.weight: Font.Bold
                    font.pixelSize: root.height * 0.10
                    color: "white"
                    text: "pair at"
                }
            }
            Item {
                id: urlItem
                anchors.top: screenCenter.bottom
                anchors.topMargin: 24
                anchors.left: pairAtItem.right
                anchors.leftMargin: Kirigami.Units.smallSpacing * 3
                width: parent.width
                height: pairAtText.paintedHeight

                Text {
                    id: urlText
                    width: parent.width
                    horizontalAlignment: Text.AlignLeft
                    verticalAlignment: Text.AlignVCenter
                    wrapMode: Text.WordWrap
                    elide: Text.ElideRight
                    font.family: "Noto Sans"
                    font.weight: Font.Bold
                    font.pixelSize: root.height * 0.10
                    color: "#2C3E50"
                    text: "mycroft.ai/pair"
                }
            }
        }
    }
}
