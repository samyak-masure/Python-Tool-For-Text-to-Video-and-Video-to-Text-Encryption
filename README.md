# About this project on encryption techniques using python

This project is about building simple encryption and decryption tools in Python.
It lets you hide a secret message inside a video or image using the encoder and later reveal it with the decoder.
The whole thing runs through an easy and minimal GUI made with Tkinter.


FEATURES

1. Encoder Module

   Lets you select any video or image and insert a hidden message inside it.

   Uses basic encryption logic to mix message data with image or video frames.

   Creates an encoded output file that looks normal but carries secret text.

2. Decoder Module

   Reads the encoded file and extracts the hidden message.

   Displays the message in a simple text area on the GUI.

   Works with the same metadata or reference file used during encoding.

3. GUI Interface

   Built using Tkinter, so it’s light and easy to run on any system.

   Buttons for selecting files, encoding, decoding, and viewing results.

   Uses OpenCV, NumPy, and PIL for handling media smoothly.

4. Learning

   Helps understand how data hiding (steganography) works.

   Shows how Python can combine logic, visuals, and GUI in one project.
