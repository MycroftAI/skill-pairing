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
                text: "Select Backend"
                color: "#ff0000"
            }
        }

        Item {
            anchors.top: topArea.bottom
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            anchors.margins: Kirigami.Units.largeSpacing
            
            ColumnLayout {
                anchors.fill: parent
                spacing: Kirigami.Units.smallSpacing
                
                Label {
                    id: warnText
                    Layout.fillWidth: true
                    wrapMode: Text.WordWrap
                    font.pixelSize: width * 0.05
                    text: "A backend provides services used by Mycroft Core to manage devices, skills and settings. Select the backend type you would like to use with your OVOS Install."
                }
                
                Item {
                    Layout.fillWidth: true
                    Layout.preferredHeight: Kirigami.Units.largeSpacing
                }
                                
                Button {
                    id: bt1
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    
                    background: Rectangle {
                        color: bt1.down ? "#14415E" : "#34a4eb"
                    }
                    
                    contentItem: Kirigami.Heading {
                        width: parent.width
                        height: parent.height
                        verticalAlignment: Text.AlignVCenter
                        horizontalAlignment: Text.AlignHCenter
                        wrapMode: Text.WordWrap
                        elide: Text.ElideRight
                        level: 3
                        text: "Mycroft Backend (Default)"
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
                        color: bt2.down ? "#BC4729" : "#eb5934"
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
