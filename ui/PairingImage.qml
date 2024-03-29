// Copyright 2021, Mycroft AI Inc.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//    http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

/*
Abstract component for SVGs.

This code is specific to the Mark II device.  It uses a grid of 16x16 pixel
squares for alignment of items.  The image is wrapped in a bounding box for
alignment purposes.
*/
import QtQuick 2.4
import QtQuick.Controls 2.3

Item {
    property alias imageSource: pairingImage.source
    property int heightUnits
    property int widthUnits

    height: gridUnit * heightUnits
    width: gridUnit * widthUnits

        Image {
            id: pairingImage
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.top: parent.top
            fillMode: Image.PreserveAspectFit
            height: gridUnit * heightUnits
        }
}
