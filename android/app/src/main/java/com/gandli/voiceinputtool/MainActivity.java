package com.gandli.voiceinputtool;

import android.app.Activity;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.content.pm.PackageManager;
import android.hardware.usb.UsbAccessory;
import android.hardware.usb.UsbManager;
import android.os.Bundle;
import android.os.ParcelFileDescriptor;
import android.speech.RecognitionListener;
import android.speech.RecognizerIntent;
import android.speech.SpeechRecognizer;
import android.util.Log;
import android.view.View;
import android.widget.Button;
import android.widget.TextView;
import android.widget.Toast;
import android.app.PendingIntent;

import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.util.ArrayList;
import java.util.List;

public class MainActivity extends Activity implements RecognitionListener {
    
    private static final String TAG = "VoiceInputTool";
    private static final int REQUEST_VOICE_RECOGNITION = 1001;
    
    private UsbManager mUsbManager;
    private UsbAccessory mAccessory;
    private ParcelFileDescriptor mFileDescriptor;
    private FileOutputStream mOutputStream;
    private FileInputStream mInputStream;
    
    private Button mRecordButton;
    private TextView mStatusText;
    private TextView mLanguageText;
    private boolean mIsConnected = false;
    
    private SpeechRecognizer mSpeechRecognizer;
    private Intent mSpeechIntent;
    private boolean mIsListening = false;
    
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);
        
        mRecordButton = findViewById(R.id.record_button);
        mStatusText = findViewById(R.id.status_text);
        mLanguageText = findViewById(R.id.language_text);
        
        mUsbManager = (UsbManager) getSystemService(Context.USB_SERVICE);
        
        // Initialize speech recognizer
        if (SpeechRecognizer.isRecognitionAvailable(this)) {
            mSpeechRecognizer = SpeechRecognizer.createSpeechRecognizer(this);
            mSpeechRecognizer.setRecognitionListener(this);
            mSpeechIntent = new Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH);
            mSpeechIntent.putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM);
            mSpeechIntent.putExtra(RecognizerIntent.EXTRA_PROMPT, "Speak now...");
        } else {
            Toast.makeText(this, "Voice recognition not available on this device", Toast.LENGTH_LONG).show();
            Log.w(TAG, "Speech recognition not available");
        }
        
        // Check if USB accessory is already connected
        checkUsbAccessory();
        
        mRecordButton.setOnClickListener(v -> toggleRecording());
        
        updateUI();
    }
    
    private void checkUsbAccessory() {
        UsbAccessory[] accessories = mUsbManager.getAccessoryList();
        if (accessories != null && accessories.length > 0) {
            mAccessory = accessories[0];
            if (!mUsbManager.hasPermission(mAccessory)) {
                // Request permission
                PendingIntent permissionIntent = PendingIntent.getBroadcast(this, 0, 
                    new Intent("com.gandli.voiceinputtool.USB_PERMISSION"), 
                    PendingIntent.FLAG_IMMUTABLE);
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
                
                // Start listening for incoming commands
                new Thread(() -> {
                    try {
                        readFromComputer();
                    } catch (IOException e) {
                        Log.e(TAG, "Error reading from computer", e);
                    }
                }).start();
            }
        } catch (IOException e) {
            Log.e(TAG, "Failed to open USB accessory", e);
            runOnUiThread(() -> {
                mStatusText.setText("USB open failed: " + e.getMessage());
                Toast.makeText(this, "USB open failed", Toast.LENGTH_SHORT).show();
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
        
        if (mSpeechRecognizer != null) {
            mSpeechRecognizer.destroy();
            mSpeechRecognizer = null;
        }
        
        mInputStream = null;
        mOutputStream = null;
        mFileDescriptor = null;
        mIsConnected = false;
        mIsListening = false;
        runOnUiThread(this::updateUI);
    }
    
    private void toggleRecording() {
        if (!mIsConnected) {
            Toast.makeText(this, "Please connect to computer first", Toast.LENGTH_SHORT).show();
            return;
        }
        
        if (mIsListening) {
            stopRecording();
        } else {
            startRecording();
        }
    }
    
    private void startRecording() {
        if (mSpeechRecognizer == null) {
            Toast.makeText(this, "Voice recognition not available", Toast.LENGTH_SHORT).show();
            return;
        }
        
        try {
            mSpeechIntent.putExtra(RecognizerIntent.EXTRA_LANGUAGE, 
                getPreferredLanguage());
            mSpeechRecognizer.startListening(mSpeechIntent);
            mIsListening = true;
            Log.d(TAG, "Started listening for speech");
            runOnUiThread(() -> {
                mRecordButton.setText("Stop Recording");
                mStatusText.setText("Listening...");
                Toast.makeText(MainActivity.this, "Listening...", Toast.LENGTH_SHORT).show();
            });
        } catch (Exception e) {
            Log.e(TAG, "Error starting speech recognition", e);
            runOnUiThread(() -> {
                mStatusText.setText("Listening error");
                Toast.makeText(this, "Speech recognition error", Toast.LENGTH_SHORT).show();
            });
        }
    }
    
    private void stopRecording() {
        if (mSpeechRecognizer != null && mIsListening) {
            try {
                mSpeechRecognizer.stopListening();
                mIsListening = false;
                Log.d(TAG, "Stopped listening for speech");
                runOnUiThread(() -> {
                    mRecordButton.setText("Start Recording");
                    mStatusText.setText("Connected to computer");
                    Toast.makeText(this, "Stopped listening", Toast.LENGTH_SHORT).show();
                });
            } catch (Exception e) {
                Log.e(TAG, "Error stopping speech recognition", e);
            }
        }
    }
    
    private void readFromComputer() throws IOException {
        byte[] buffer = new byte[1024];
        int bytes;
        
        while (mInputStream != null) {
            try {
                if ((bytes = mInputStream.read(buffer)) > 0) {
                    String command = new String(buffer, 0, bytes).trim();
                    Log.d(TAG, "Received command from computer: " + command);
                    
                    // Process commands from computer
                    if ("STOP".equalsIgnoreCase(command)) {
                        runOnUiThread(this::stopRecording);
                    } else if ("START".equalsIgnoreCase(command)) {
                        runOnUiThread(this::startRecording);
                    }
                }
            } catch (IOException e) {
                if (mIsConnected) {
                    Log.e(TAG, "Error reading from computer", e);
                }
                break;
            }
        }
    }
    
    private void sendTextToComputer(String text) {
        if (mOutputStream != null && text != null && !text.isEmpty()) {
            try {
                String message = text + "\n";
                mOutputStream.write(message.getBytes("UTF-8"));
                mOutputStream.flush();
                Log.d(TAG, "Sent text to computer: " + text);
            } catch (IOException e) {
                Log.e(TAG, "Failed to send text to computer", e);
                runOnUiThread(() -> {
                    mStatusText.setText("USB send failed");
                    Toast.makeText(this, "USB communication failed", Toast.LENGTH_SHORT).show();
                });
            }
        }
    }
    
    private String getPreferredLanguage() {
        // Try to detect system language
        String language = getResources().getConfiguration().locale.getLanguage();
        if ("zh".equals(language)) {
            return "zh-CN";
        } else if ("en".equals(language)) {
            return "en-US";
        }
        return "en-US";
    }
    
    private void updateUI() {
        runOnUiThread(() -> {
            if (mIsConnected) {
                mRecordButton.setEnabled(true);
                mLanguageText.setVisibility(View.VISIBLE);
                mRecordButton.setText(mIsListening ? "Stop Recording" : "Start Recording");
            } else {
                mRecordButton.setEnabled(false);
                mLanguageText.setVisibility(View.GONE);
                mRecordButton.setText("Connect First");
            }
        });
    }
    
    // RecognitionListener callbacks
    @Override
    public void onReadyForSpeech(Bundle params) {
        Log.d(TAG, "Ready for speech");
    }
    
    @Override
    public void onBeginningOfSpeech() {
        Log.d(TAG, "Speech beginning");
    }
    
    @Override
    public void onRmsChanged(float rmsdB) {
        // Could use this for visual feedback
    }
    
    @Override
    public void onBufferReceived(byte[] buffer) {
        // Process buffer if needed
    }
    
    @Override
    public void onEndOfSpeech() {
        Log.d(TAG, "Speech ended");
        runOnUiThread(() -> mStatusText.setText("Processing..."));
    }
    
    @Override
    public void onError(int error) {
        Log.e(TAG, "Speech recognition error: " + error);
        String errorMessage = getErrorMessage(error);
        runOnUiThread(() -> {
            mStatusText.setText("Error: " + errorMessage);
            mRecordButton.setText("Start Recording");
            mIsListening = false;
        });
    }
    
    private String getErrorMessage(int error) {
        switch (error) {
            case 1: return "Network error";
            case 2: return "Audio error";
            case 3: return "Server error";
            case 4: return "Client error";
            case 5: return "No speech input";
            case 6: return "Speak timeout";
            case 7: return "Max matches reached";
            case 8: return "Language not supported";
            default: return "Unknown error";
        }
    }
    
    @Override
    public void onResults(Bundle results) {
        ArrayList<String> matches = results.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION);
        if (matches != null && !matches.isEmpty()) {
            String recognizedText = matches.get(0);
            Log.d(TAG, "Recognized text: " + recognizedText);
            
            // Send text to computer via USB
            sendTextToComputer(recognizedText);
            
            runOnUiThread(() -> {
                mLanguageText.setText("Sent: " + recognizedText);
                Toast.makeText(this, "Text sent to computer", Toast.LENGTH_SHORT).show();
            });
        }
    }
    
    @Override
    public void onPartialResults(Bundle partialResults) {
        ArrayList<String> matches = partialResults.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION);
        if (matches != null && !matches.isEmpty()) {
            String partialText = matches.get(0);
            Log.d(TAG, "Partial text: " + partialText);
            runOnUiThread(() -> mLanguageText.setText("Partial: " + partialText));
        }
    }
    
    @Override
    public void onEvent(int eventType, Bundle params) {
        // Handle custom events
    }
    
    @Override
    protected void onDestroy() {
        super.onDestroy();
        closeAccessory();
    }
}
