package com.gandli.voiceinputtool;

import android.app.Activity;
import android.app.AlertDialog;
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
import android.widget.ArrayAdapter;
import android.widget.Button;
import android.widget.Spinner;
import android.widget.TextView;
import android.widget.Toast;
import android.app.PendingIntent;

import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.util.ArrayList;
import java.util.Locale;

public class MainActivity extends Activity {
    
    private static final String TAG = "VoiceInputTool";
    private static final int REQUEST_VOICE_RECOGNITION = 1001;
    private static final String ACTION_USB_PERMISSION = "com.gandli.voiceinputtool.USB_PERMISSION";
    
    private UsbManager mUsbManager;
    private UsbAccessory mAccessory;
    private ParcelFileDescriptor mFileDescriptor;
    private FileOutputStream mOutputStream;
    private FileInputStream mInputStream;
    
    private Button mRecordButton;
    private TextView mStatusText;
    private Spinner mLanguageSpinner;
    private boolean mIsConnected = false;
    
    // USB broadcast receiver for connection events
    private final BroadcastReceiver mUsbReceiver = new BroadcastReceiver() {
        public void onReceive(Context context, Intent intent) {
            String action = intent.getAction();
            
            if (UsbManager.ACTION_USB_ACCESSORY_ATTACHED.equals(action)) {
                Log.d(TAG, "USB accessory attached");
                synchronized (this) {
                    checkUsbAccessory();
                }
            } else if (UsbManager.ACTION_USB_ACCESSORY_DETACHED.equals(action)) {
                Log.d(TAG, "USB accessory detached");
                synchronized (this) {
                    closeAccessory();
                    mIsConnected = false;
                    runOnUiThread(() -> {
                        mStatusText.setText("USB disconnected - Please reconnect");
                        mRecordButton.setEnabled(false);
                        mRecordButton.setText("Connect First");
                    });
                }
            } else if (ACTION_USB_PERMISSION.equals(action)) {
                synchronized (this) {
                    if (intent.getBooleanExtra(UsbManager.EXTRA_PERMISSION_GRANTED, false)) {
                        Log.d(TAG, "USB permission granted");
                        openAccessory();
                    } else {
                        Log.w(TAG, "USB permission denied");
                        runOnUiThread(() -> 
                            Toast.makeText(MainActivity.this, "USB permission denied", Toast.LENGTH_SHORT).show()
                        );
                    }
                }
            }
        }
    };
    
    // Supported languages for voice recognition
    private static final String[] LANGUAGES = {
        "Auto-detect",
        "Chinese (Simplified)",
        "Chinese (Traditional)",
        "English (US)",
        "English (UK)",
        "Japanese",
        "Korean"
    };
    
    private static final String[] LANGUAGE_CODES = {
        "",
        "zh-CN",
        "zh-TW",
        "en-US",
        "en-GB",
        "ja-JP",
        "ko-KR"
    };
    
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);
        
        mRecordButton = findViewById(R.id.record_button);
        mStatusText = findViewById(R.id.status_text);
        mLanguageSpinner = findViewById(R.id.language_spinner);
        
        // Setup language spinner
        ArrayAdapter<String> adapter = new ArrayAdapter<>(
            this, 
            android.R.layout.simple_spinner_item, 
            LANGUAGES
        );
        adapter.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item);
        mLanguageSpinner.setAdapter(adapter);
        
        mUsbManager = (UsbManager) getSystemService(USB_SERVICE);
        
        // Register USB broadcast receiver
        IntentFilter filter = new IntentFilter();
        filter.addAction(UsbManager.ACTION_USB_ACCESSORY_ATTACHED);
        filter.addAction(UsbManager.ACTION_USB_ACCESSORY_DETACHED);
        filter.addAction(ACTION_USB_PERMISSION);
        registerReceiver(mUsbReceiver, filter);
        
        // Check if USB accessory is already connected
        checkUsbAccessory();
        
        mRecordButton.setOnClickListener(v -> {
            if (mIsConnected) {
                startVoiceRecognition();
            } else {
                // Try to reconnect
                checkUsbAccessory();
            }
        });
        
        // Long press to show settings
        mRecordButton.setOnLongClickListener(v -> {
            showLanguageDialog();
            return true;
        });
        
        updateUI();
    }
    
    private void showLanguageDialog() {
        new AlertDialog.Builder(this)
            .setTitle("Select Language")
            .setItems(LANGUAGES, (dialog, which) -> {
                mLanguageSpinner.setSelection(which);
                Toast.makeText(this, "Language set to: " + LANGUAGES[which], Toast.LENGTH_SHORT).show();
            })
            .show();
    }
    
    private void checkUsbAccessory() {
        UsbAccessory[] accessories = mUsbManager.getAccessoryList();
        if (accessories != null && accessories.length > 0) {
            mAccessory = accessories[0];
            if (!mUsbManager.hasPermission(mAccessory)) {
                // Request permission
                PendingIntent permissionIntent = PendingIntent.getBroadcast(
                    this, 
                    0, 
                    new Intent(ACTION_USB_PERMISSION), 
                    PendingIntent.FLAG_IMMUTABLE
                );
                mUsbManager.requestPermission(mAccessory, permissionIntent);
            } else {
                openAccessory();
            }
        } else {
            Log.d(TAG, "No USB accessory found");
            runOnUiThread(() -> {
                mStatusText.setText("Not connected - Please connect USB");
            });
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
                
                // Send ready signal
                sendTextToComputer("[READY]");
                
                runOnUiThread(this::updateUI);
            }
        } catch (IOException e) {
            Log.e(TAG, "Failed to open USB accessory", e);
            runOnUiThread(() -> {
                mStatusText.setText("Connection failed");
            });
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
        
        // Set language based on selection
        int selectedLang = mLanguageSpinner.getSelectedItemPosition();
        String languageCode = LANGUAGE_CODES[selectedLang];
        
        if (languageCode != null && !languageCode.isEmpty()) {
            intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE, languageCode);
            intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE_PREFERENCE, languageCode);
            Log.d(TAG, "Using language: " + languageCode);
        } else {
            // Auto-detect based on device locale
            Locale defaultLocale = Locale.getDefault();
            intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE, defaultLocale.toLanguageTag());
            Log.d(TAG, "Using auto-detect language: " + defaultLocale.toLanguageTag());
        }
        
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
                    String recognizedText = results.get(0); // Best result
                    Log.d(TAG, "Recognized text: " + recognizedText);
                    
                    // Send text to computer via USB
                    sendTextToComputer(recognizedText);
                    
                    runOnUiThread(() -> {
                        mStatusText.setText("Sent: " + recognizedText);
                        Toast.makeText(MainActivity.this, "Text sent to computer", Toast.LENGTH_SHORT).show();
                    });
                }
            } else if (resultCode == RESULT_CANCELED) {
                runOnUiThread(() -> {
                    mStatusText.setText("Recognition cancelled");
                });
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
    protected void onResume() {
        super.onResume();
        // Check USB connection when resuming
        if (!mIsConnected) {
            checkUsbAccessory();
        }
    }
    
    @Override
    protected void onDestroy() {
        super.onDestroy();
        closeAccessory();
        try {
            unregisterReceiver(mUsbReceiver);
        } catch (Exception e) {
            Log.w(TAG, "Failed to unregister receiver", e);
        }
    }
}