package com.gandli.voiceinputtool;

import android.app.Activity;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
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
    
    private VoiceProcessor mVoiceProcessor;
    private BroadcastReceiver mUsbReceiver;
    
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);
        
        mRecordButton = findViewById(R.id.record_button);
        mStatusText = findViewById(R.id.status_text);
        
        mUsbManager = (UsbManager) getSystemService(USB_SERVICE);
        mVoiceProcessor = new VoiceProcessor(this);
        
        // Register USB receiver for connection events
        mUsbReceiver = new BroadcastReceiver() {
            @Override
            public void onReceive(Context context, Intent intent) {
                String action = intent.getAction();
                if (UsbManager.ACTION_USB_ACCESSORY_ATTACHED.equals(action)) {
                    checkUsbAccessory();
                } else if (UsbManager.ACTION_USB_ACCESSORY_DETACHED.equals(action)) {
                    closeAccessory();
                }
            }
        };
        
        IntentFilter filter = new IntentFilter();
        filter.addAction(UsbManager.ACTION_USB_ACCESSORY_ATTACHED);
        filter.addAction(UsbManager.ACTION_USB_ACCESSORY_DETACHED);
        registerReceiver(mUsbReceiver, filter);
        
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
                
                // Start listening for incoming commands from computer
                startCommandListener();
                
                runOnUiThread(this::updateUI);
            }
        } catch (IOException e) {
            Log.e(TAG, "Failed to open USB accessory", e);
            runOnUiThread(() -> {
                mStatusText.setText("USB connection failed");
                Toast.makeText(MainActivity.this, "USB connection failed", Toast.LENGTH_SHORT).show();
            });
        }
    }
    
    private void startCommandListener() {
        new Thread(() -> {
            byte[] buffer = new byte[1024];
            while (mIsConnected && mInputStream != null) {
                try {
                    int bytesRead = mInputStream.read(buffer);
                    if (bytesRead > 0) {
                        String command = new String(buffer, 0, bytesRead).trim();
                        Log.d(TAG, "Received command: " + command);
                        
                        // Process commands from computer
                        if ("GET_SPEAKER_COUNT".equals(command)) {
                            sendTextToComputer("SPEAKER_COUNT:" + mVoiceProcessor.getSpeakerCount());
                        }
                    }
                } catch (IOException e) {
                    Log.e(TAG, "Error reading from USB", e);
                    break;
                }
            }
        }).start();
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
        
        // Use our enhanced voice processor
        mVoiceProcessor.startVoiceRecognition(REQUEST_VOICE_RECOGNITION);
    }
    
    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        
        if (requestCode == REQUEST_VOICE_RECOGNITION) {
            mVoiceProcessor.handleVoiceRecognitionResult(resultCode, data, text -> {
                if (text != null && !text.isEmpty()) {
                    Log.d(TAG, "Processed text: " + text);
                    
                    // Send processed text to computer via USB
                    sendTextToComputer(text);
                    
                    runOnUiThread(() -> {
                        mStatusText.setText("Sent: " + text);
                        Toast.makeText(MainActivity.this, "Text sent to computer", Toast.LENGTH_SHORT).show();
                    });
                } else {
                    runOnUiThread(() -> {
                        mStatusText.setText("Recognition failed");
                        Toast.makeText(MainActivity.this, "Recognition failed", Toast.LENGTH_SHORT).show();
                    });
                }
            });
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
        if (mUsbReceiver != null) {
            unregisterReceiver(mUsbReceiver);
        }
        closeAccessory();
    }
}