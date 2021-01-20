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
    
    ListModel {
        id: backendFeatureList
        ListElement {
            text: "Requires Pairing"
        }
        ListElement {
            text: "Uses Default Mycroft STT"
        }
        ListElement {
            text: "Provides Web Skill Settings Interface"
        }
        ListElement {
            text: "Provides Web Device Configuration Interface"
        }
    }

    Rectangle {
        color: "#000000"
        anchors.fill: parent
    
        Item {
            id: topArea
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.leftMargin: Kirigami.Units.largeSpacing
            anchors.rightMargin: Kirigami.Units.largeSpacing
            height: Kirigami.Units.gridUnit * 2
            
            Kirigami.Heading {
                id: brightnessSettingPageTextHeading
                level: 1
                wrapMode: Text.WordWrap
                anchors.centerIn: parent
                font.bold: true
                text: "Mycroft Backend"
                color: "#ff0000"
            }
        }

        Item {
            anchors.top: topArea.bottom
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: areaSep.top
            anchors.margins: Kirigami.Units.largeSpacing
            
            ColumnLayout {
                anchors.fill: parent
                spacing: Kirigami.Units.smallSpacing
                
                Label {
                    id: warnText
                    Layout.fillWidth: true
                    wrapMode: Text.WordWrap
                    font.pixelSize: width * 0.040
                    text: "The official backend service provided by Mycroft AI."
                }
                
                Item {
                    Layout.fillWidth: true
                    Layout.preferredHeight: Kirigami.Units.largeSpacing
                }
                
                ListView {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    model: backendFeatureList
                    currentIndex: -1
                    delegate: Kirigami.BasicListItem {
                        label: model.text
                        icon: Qt.resolvedUrl("icons/info-circle.svg")
                    } 
                }
            }
        }

        Kirigami.Separator {
            id: areaSep
            anchors.bottom: bottomArea.top
            anchors.bottomMargin: Kirigami.Units.largeSpacing
            anchors.left: parent.left
            anchors.right: parent.right
            height: 1
        }

        RowLayout {
            id: bottomArea
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            anchors.margins: Kirigami.Units.largeSpacing
            height: Kirigami.Units.gridUnit * 2.5
            
            Button {
                Layout.fillWidth: true
                Layout.fillHeight: true
                
                background: Rectangle {
                    color: bottomArea.down ? "#C89900" : "#fac000"
                }

                contentItem: Kirigami.Heading {
                    level: 3
                    wrapMode: Text.WordWrap
                    font.bold: true
                    text: "Back"
                    verticalAlignment: Text.AlignVCenter
                    horizontalAlignment: Text.AlignHCenter
                }
                
                onClicked: {
                    triggerGuiEvent("mycroft.return.select.backend", {"page": "mycroft"})
                }
            }
            
            Button {
                Layout.fillWidth: true
                Layout.fillHeight: true
                
                background: Rectangle {
                    color: bottomArea.down ? "#023B43" : "#09c5e0"
                }

                contentItem: Kirigami.Heading {
                    level: 3
                    wrapMode: Text.WordWrap
                    font.bold: true
                    text: "Confirm Backend >"
                    verticalAlignment: Text.AlignVCenter
                    horizontalAlignment: Text.AlignHCenter
                }
                
                onClicked: {
                    triggerGuiEvent("mycroft.device.confirm.backend", {"backend": "default"})
                }
            }
        }
    }
} 
