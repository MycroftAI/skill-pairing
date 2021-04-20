/*
 * Copyright 2018 Aditya Mehra <aix.m@outlook.com>
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
import org.kde.kirigami 2.5 as Kirigami
import org.kde.plasma.core 2.0 as PlasmaCore
import Mycroft 1.0 as Mycroft

Mycroft.Delegate {
    id: backendView
    anchors.fill: parent
    leftPadding: 0
    rightPadding: 0
    topPadding: 0
    bottomPadding: 0
    skillBackgroundColorOverlay: Qt.rgba(0, 0, 0, 1)
    property bool horizontalMode: backendView.width > backendView.height ? 1 :0

    Rectangle {
        color: Qt.rgba(0, 0, 0, 1)
        anchors.fill: parent
        anchors.margins: Mycroft.Units.gridUnit * 2

        GridLayout {
            anchors.fill: parent
            z: 1
            columns: horizontalMode ? 2 : 1
            columnSpacing: Kirigami.Units.largeSpacing
            Layout.alignment: horizontalMode ? Qt.AlignVCenter : Qt.AlignTop

            ColumnLayout {
                Layout.maximumWidth: horizontalMode ? parent.width / 2 : parent.width
                Layout.preferredHeight: horizontalMode ? parent.height : parent.height / 2
                Layout.alignment: horizontalMode ? Qt.AlignVCenter : Qt.AlignTop

                Label {
                    id: selBText
                    Layout.fillWidth: true
                    wrapMode: Text.WordWrap
                    font.bold: true
                    font.pixelSize: backendView.width * 0.05
                    color: "#ff0000"
                    text: "Select Your Backend"
                }

                Label {
                    id: warnText
                    Layout.fillWidth: true
                    Layout.alignment: Qt.AlignTop
                    wrapMode: Text.WordWrap
                    font.pixelSize: backendView.width * 0.04
                    color: "white"
                    text: "A backend provides services used by Mycroft Core"
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true

                Button {
                    id: bt1
                    Layout.fillWidth: true
                    Layout.fillHeight: true

                    background: Rectangle {
                        color: bt1.down ? "#14415E" : "#22a7f0"
                        radius: 10
                    }

                    contentItem: Kirigami.Heading {
                        width: parent.width
                        height: parent.height
                        verticalAlignment: Text.AlignVCenter
                        horizontalAlignment: Text.AlignHCenter
                        wrapMode: Text.WordWrap
                        elide: Text.ElideRight
                        level: 3
                        text: "Mycroft Backend"
                    }

                    onClicked: {
                        triggerGuiEvent("mycroft.device.set.backend",
                        {"backend": "selene"})
                    }
                }

                Button {
                    id: bt2
                    Layout.fillWidth: true
                    Layout.fillHeight: true

                    background: Rectangle {
                        color: bt2.down ? "#BC4729" : "#eb4934"
                        radius: 10
                    }

                    contentItem: Kirigami.Heading {
                        width: parent.width
                        height: parent.height
                        verticalAlignment: Text.AlignVCenter
                        horizontalAlignment: Text.AlignHCenter
                        wrapMode: Text.WordWrap
                        elide: Text.ElideRight
                        level: 3
                        text: "Local Backend"
                    }

                    onClicked: {
                        triggerGuiEvent("mycroft.device.set.backend",
                        {"backend": "local"})
                    }
                }
            }
        }
    }
} 
