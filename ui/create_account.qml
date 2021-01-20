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

/* Define a screen requesting that a user create an account before pairing. */
Mycroft.Delegate {
    id: root
    leftPadding: 0
    rightPadding: 0
    bottomPadding: 0
    topPadding: 0

    Rectangle {
        id: background
        color: "#22a7f0"
        width: parent.width
        height: parent.height

        Item {
            id: instructions
            anchors.fill: parent
            anchors.margins: Kirigami.Units.largeSpacing

            Item {
                id: instructionItem
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.topMargin: 36
                height: instructionText.paintedHeight

                Text {
                    id: instructionText
                    width: parent.width
                    horizontalAlignment: Text.AlignHCenter
                    wrapMode: Text.WordWrap
                    elide: Text.ElideRight
                    font.family: "Noto Sans"
                    font.weight: Font.Bold
                    fontSizeMode: Text.HorizontalFit
                    minimumPixelSize: 70
                    font.pixelSize: Math.max(root.height * 0.25, minimumPixelSize)
                    color: "white"
                    text: "Create a Mycroft account"
                }
            }
            Item {
                id: urlItem
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: instructionItem.bottom
                anchors.topMargin: 36
                height: urlText.paintedHeight

                Text {
                    id: urlText
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignTop
                    width: parent.width
                    font.family: "Noto Sans"
                    font.weight: Font.Bold
                    fontSizeMode: Text.HorizontalFit
                    font.pixelSize: root.height * 0.10
                    color: "#2C3E50"
                    text: "account.mycroft.ai"
                }
            }
        }
    }
}
