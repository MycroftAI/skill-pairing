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

Mycroft.Delegate {
    id: root
    property var code: sessionData.code
    property var txtcolor: sessionData.txtcolor
    property var backendurl: sessionData.backendurl
    leftPadding: 0
    rightPadding: 0
    bottomPadding: 0
    topPadding: 0
    
    Rectangle {
        color: "#000000"
        anchors.fill: parent
        
        ColumnLayout {
            id: colLay
            anchors.fill: parent
            anchors.margins: Kirigami.Units.largeSpacing
            
            RowLayout {
                Layout.fillWidth: true
                Layout.minimumHeight: colLay.height * 0.075
                Layout.alignment: Qt.AlignHCenter
                                    
                Kirigami.Heading {
                    id: sentence
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                    wrapMode: Text.WordWrap
                    elide: Text.ElideRight
                    font.family: "Noto Sans"
                    font.bold: true
                    font.weight: Font.Bold
                    font.pixelSize: colLay.height * 0.05
                    color: "white"
                    text: "Visit"
                }
                
                Kirigami.Heading {
                    id: backendurl
                    horizontalAlignment: Text.AlignLeft
                    verticalAlignment: Text.AlignVCenter
                    wrapMode: Text.WordWrap
                    elide: Text.ElideRight
                    font.family: "Noto Sans"
                    font.bold: true
                    font.weight: Font.Bold
                    font.pixelSize: colLay.height * 0.05
                    color: root.txtcolor
                    text: root.backendurl
                }
            }
        
            Kirigami.Heading {
                id: sentence3
                Layout.fillWidth: true
                Layout.alignment: Qt.AlignLeft
                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.WordWrap
                elide: Text.ElideRight
                font.family: "Noto Sans"
                font.bold: true
                font.weight: Font.Bold
                font.pixelSize: parent.height * 0.05
                color: "white"
                text: "to pair this device"
            }
                
            Image {
                id: img
                source: Qt.resolvedUrl("phone.png")
                fillMode: Image.PreserveAspectFit
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.leftMargin: Kirigami.Units.largeSpacing
                Layout.rightMargin: Kirigami.Units.largeSpacing
                Layout.alignment: Qt.AlignHCenter | Qt.AlignBottom
            }
            
            
            Kirigami.Heading {
                id: entercode
                Layout.fillWidth: true
                Layout.alignment: Qt.AlignLeft
                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.WordWrap
                elide: Text.ElideRight
                font.family: "Noto Sans"
                font.bold: true
                font.weight: Font.Bold
                font.pixelSize: parent.height * 0.05
                color: "white"
                text: "Enter the code"
            }
            
            Kirigami.Heading {
                id: pairingcode
                Layout.fillWidth: true
                Layout.alignment: Qt.AlignLeft
                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.WordWrap
                elide: Text.ElideRight
                font.family: "Noto Sans"
                font.bold: true
                font.weight: Font.Bold
                font.pixelSize: parent.height * 0.075
                color: root.txtcolor
                text: root.code
            }
        }
    }
}  
