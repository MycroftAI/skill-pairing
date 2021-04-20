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
    property bool horizontalMode: root.width > root.height ? 1 :0

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
        anchors.margins: Mycroft.Units.gridUnit * 2

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
                font.pixelSize: horizontalMode ? backendView.width * 0.035 : backendView.height * 0.040
                text: "Mycroft Backend"
                color: "#ff0000"
            }
        }

        Item {
            anchors.top: topArea.bottom
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: bottomArea.top
            anchors.margins: Kirigami.Units.smallSpacing

            ColumnLayout {
                anchors.fill: parent
                spacing: Kirigami.Units.smallSpacing

                Label {
                    id: warnText
                    Layout.fillWidth: true
                    horizontalAlignment: Text.AlignHCenter
                    color: "white"
                    wrapMode: Text.WordWrap
                    font.pixelSize: horizontalMode ? backendView.width * 0.035 : backendView.height * 0.040
                    text: "The official backend service provided by Mycroft AI"
                }

                Item {
                    Layout.fillWidth: true
                    Layout.preferredHeight: Kirigami.Units.largeSpacing
                }

                ListView {
                    id: qViewL
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    model: backendFeatureList
                    clip: true
                    currentIndex: -1
                    spacing: 5
                    property int cellWidth: qViewL.width
                    property int cellHeight: qViewL.height / 4.6
                    delegate: Rectangle {
                        width: qViewL.cellWidth
                        height: qViewL.cellHeight
                        radius: 10
                        color: Qt.rgba(0.1, 0.1, 0.1, 0.9)

                        Rectangle {
                            id: symb
                            anchors.left: parent.left
                            anchors.leftMargin: Kirigami.Units.smallSpacing
                            anchors.verticalCenter: parent.verticalCenter
                            height: parent.height - Kirigami.Units.largeSpacing
                            width: Kirigami.Units.iconSizes.medium
                            color: "#e31525"
                            radius: width
                        }

                        Label {
                            id: cItm
                            anchors.left: symb.right
                            anchors.leftMargin: Kirigami.Units.largeSpacing
                            anchors.right: parent.right
                            anchors.top: parent.top
                            anchors.bottom: parent.bottom
                            wrapMode: Text.WordWrap
                            anchors.margins: Kirigami.Units.smallSpacing
                            verticalAlignment: Text.AlignVCenter
                            color: "white"
                            text: model.text
                        }
                    }
                }
            }
        }

        RowLayout {
            id: bottomArea
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            anchors.topMargin: Kirigami.Units.largeSpacing
            anchors.leftMargin: Kirigami.Units.largeSpacing
            anchors.rightMargin: Kirigami.Units.largeSpacing
            height: Kirigami.Units.gridUnit * 2

            Button {
                id: btnba1
                Layout.fillWidth: true
                Layout.fillHeight: true

                background: Rectangle {
                    color: btnba1.down ? "#323232" : "#595959"
                    radius: 10
                }

                contentItem: Kirigami.Heading {
                    level: 3
                    wrapMode: Text.WordWrap
                    font.bold: true
                    color: "white"
                    text: "Back"
                    verticalAlignment: Text.AlignVCenter
                    horizontalAlignment: Text.AlignHCenter
                }

                onClicked: {
                    triggerGuiEvent("mycroft.return.select.backend",
                    {"page": "selene"})
                }
            }

            Button {
                id: btnba2
                Layout.fillWidth: true
                Layout.fillHeight: true

                background: Rectangle {
                    color: btnba2.down ? "#53080e" : "#e31525"
                    radius: 10
                }

                contentItem: Kirigami.Heading {
                    level: 3
                    wrapMode: Text.WordWrap
                    font.bold: true
                    color: "white"
                    text: "Confirm"
                    verticalAlignment: Text.AlignVCenter
                    horizontalAlignment: Text.AlignHCenter
                }

                onClicked: {
                    triggerGuiEvent("mycroft.device.confirm.backend",
                    {"backend": "selene"})
                }
            }
        }
    }
} 
