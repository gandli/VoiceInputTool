package com.gandli.voiceinputtool;

import android.app.Activity;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.hardware.usb.UsbAccessory;
import android.hardware.usb.UsbManager;
import android.os.Bundle;
import android.os.ParcelFileDescriptor;
import android.speech.RecognizerIntent;
import android.util.Log;
import android.view.View;
import android.widget.Button;
import android.widget.TextView;
import android.widget.Toast;

import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.util.ArrayList;

public class MainActivity extends Activity {
    
    private static final String TAG = "VoiceInputTool";
    private static final int REQUEST_VOICE_RECOGNITION = 1001;
    
    private UsbManager mUsbManager;
    private UsbAccessory mAccessory;
    private ParcelFileDescriptor mFileDescriptor;
    private FileOutputStream mOutputStream;
    private FileInputStream mInputStream;
    
    private Button mRecordButton;
    private TextView mStatusText;
    private boolean mIsConnected = false;
    
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);
        
        mRecordButton = findViewById(R.id.record_button);
        mStatusText = findViewById(R.id.status_text);
        
        mUsbManager = (UsbManager) getSystemService(USB_SERVICE);
        
        // Check if USB accessory is already connected
        checkUsbAccessory();
        
        mRecordButton.setOnClickListener(v -> startVoiceRecognition());
        
        updateUI();
    }
    
    private void checkUsbAccessory() {
        UsbAccessory[] accessories = mUsbManager.getAccessoryList();
        if (accessories != null && accessories.length > 0) {
            mAccessory = accessories[0];
            if (!mUsbManager.hasPermission(mAccessory)) {
                // Request permission
                PendingIntent permissionIntent = PendingIntent.getBroadcast(this, 0, new Intent(), PendingIntent.FLAG_IMMUTABLE);
                mUsbManager.requestPermission(mAccessory, permissionIntent);
            } else {
                openAccessory();
            }
        }
    }
    
    private void openAccessory() {
        try {
            mFileDescriptor = mUsbManager.openAccessory(mAccessory);
            if (mFileDescriptor != null) {
                mInputStream = new FileInputStream(mFileDescriptor.getFileDescriptor());
                mOutputStream = new FileOutputStream(mFileDescriptor.getFileDescriptor());
                mIsConnected = true;
                Log.d(TAG, "USB accessory opened successfully");
                runOnUiThread(this::updateUI);
            }
        } catch (IOException e) {
            Log.e(TAG, "Failed to open USB accessory", e);
        }
    }
    
    private void closeAccessory() {
        try {
            if (mInputStream != null) {
                mInputStream.close();
            }
            if (mOutputStream != null) {
                mOutputStream.close();
            }
            if (mFileDescriptor != null) {
                mFileDescriptor.close();
            }
        } catch (IOException e) {
            Log.e(TAG, "Failed to close USB accessory", e);
        }
        
        mInputStream = null;
        mOutputStream = null;
        mFileDescriptor = null;
        mIsConnected = false;
        runOnUiThread(this::updateUI);
    }
    
    private void startVoiceRecognition() {
        if (!mIsConnected) {
            Toast.makeText(this, "Please connect to computer first", Toast.LENGTH_SHORT).show();
            return;
        }
        
        Intent intent = new Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH);
        intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM);
        intent.putExtra(RecognizerIntent.EXTRA_PROMPT, "Speak now...");
        
        try {
            startActivityForResult(intent, REQUEST_VOICE_RECOGNITION);
        } catch (Exception e) {
            Toast.makeText(this, "Voice recognition not available", Toast.LENGTH_SHORT).show();
            Log.e(TAG, "Voice recognition error", e);
        }
    }
    
    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        
        if (requestCode == REQUEST_VOICE_RECOGNITION) {
            if (resultCode == RESULT_OK && data != null) {
                ArrayList<String> results = data.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS);
                if (results != null && !results.isEmpty()) {
                    String recognizedText = results.get(0);
                    Log.d(TAG, "Recognized text: " + recognizedText);
                    
                    // Send text to computer via USB
                    sendTextToComputer(recognizedText);
                    
                    runOnUiThread(() -> {
                        mStatusText.setText("Sent: " + recognizedText);
                        Toast.makeText(MainActivity.this, "Text sent to computer", Toast.LENGTH_SHORT).show();
                    });
                }
            } else {
                runOnUiThread(() -> {
                    mStatusText.setText("Recognition failed");
                    Toast.makeText(MainActivity.this, "Recognition failed", Toast.LENGTH_SHORT).show();
                });
            }
        }
    }
    
    private void sendTextToComputer(String text) {
        if (mOutputStream != null) {
            try {
                // Send text with newline terminator
                String message = text + "\n";
                mOutputStream.write(message.getBytes());
                mOutputStream.flush();
                Log.d(TAG, "Sent text to computer: " + text);
            } catch (IOException e) {
                Log.e(TAG, "Failed to send text to computer", e);
                runOnUiThread(() -> {
                    mStatusText.setText("USB send failed");
                    Toast.makeText(MainActivity.this, "USB communication failed", Toast.LENGTH_SHORT).show();
                });
            }
        }
    }
    
    private void updateUI() {
        if (mIsConnected) {
            mRecordButton.setEnabled(true);
            mStatusText.setText("Connected to computer");
            mRecordButton.setText("Start Voice Input");
        } else {
            mRecordButton.setEnabled(false);
            mStatusText.setText("Not connected - Please connect USB");
            mRecordButton.setText("Connect First");
        }
    }
    
    @Override
    protected void onDestroy() {
        super.onDestroy();
        closeAccessory();
    }
}