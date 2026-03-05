package com.gandli.voiceinputtool;

import android.app.Activity;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
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
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.atomic.AtomicBoolean;

/**
 * Main activity for Voice Input Tool.
 * Manages USB accessory connection and voice recognition with improved
 * resource management and thread safety.
 */
public class MainActivity extends Activity implements RecognitionListener {
    
    private static final String TAG = "VoiceInputTool";
    private static final int REQUEST_VOICE_RECOGNITION = 1001;
    private static final String ACTION_USB_PERMISSION = "com.gandli.voiceinputtool.USB_PERMISSION";
    
    // USB Components
    private UsbManager mUsbManager;
    private UsbAccessory mAccessory;
    private ParcelFileDescriptor mFileDescriptor;
    private FileOutputStream mOutputStream;
    private FileInputStream mInputStream;
    
    // UI Components
    private Button mRecordButton;
    private TextView mStatusText;
    private TextView mLanguageText;
    
    // Thread-safe state flags
    private final AtomicBoolean mIsConnected = new AtomicBoolean(false);
    private final AtomicBoolean mIsListening = new AtomicBoolean(false);
    private final AtomicBoolean mIsDestroyed = new AtomicBoolean(false);
    
    // Speech Recognition
    private SpeechRecognizer mSpeechRecognizer;
    private Intent mSpeechIntent;
    
    // Background thread for reading from computer
    private Thread mReadThread;
    private final Object mConnectionLock = new Object();

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);
        
        initViews();
        initUsbManager();
        initSpeechRecognizer();
        checkUsbAccessory();
        updateUI();
    }
    
    /**
     * Initialize UI views and click listeners.
     */
    private void initViews() {
        mRecordButton = findViewById(R.id.record_button);
        mStatusText = findViewById(R.id.status_text);
        mLanguageText = findViewById(R.id.language_text);
        
        mRecordButton.setOnClickListener(v -> toggleRecording());
    }
    
    /**
     * Initialize USB manager.
     */
    private void initUsbManager() {
        mUsbManager = (UsbManager) getSystemService(Context.USB_SERVICE);
        if (mUsbManager == null) {
            Log.e(TAG, "Failed to get USB manager");
            showToast(R.string.usb_not_supported);
        }
    }
    
    /**
     * Initialize speech recognizer with proper error handling.
     */
    private void initSpeechRecognizer() {
        if (!SpeechRecognizer.isRecognitionAvailable(this)) {
            showToast(R.string.voice_recognition_not_available);
            Log.w(TAG, "Speech recognition not available");
            return;
        }
        
        try {
            mSpeechRecognizer = SpeechRecognizer.createSpeechRecognizer(this);
            mSpeechRecognizer.setRecognitionListener(this);
            
            mSpeechIntent = new Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH);
            mSpeechIntent.putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, 
                RecognizerIntent.LANGUAGE_MODEL_FREE_FORM);
            mSpeechIntent.putExtra(RecognizerIntent.EXTRA_PROMPT, 
                getString(R.string.voice_speak_now));
        } catch (Exception e) {
            Log.e(TAG, "Failed to initialize speech recognizer", e);
            showToast(R.string.voice_recognition_not_available);
        }
    }

    /**
     * Check if USB accessory is already connected.
     */
    private void checkUsbAccessory() {
        if (mUsbManager == null) return;
        
        UsbAccessory[] accessories = mUsbManager.getAccessoryList();
        if (accessories != null && accessories.length > 0) {
            mAccessory = accessories[0];
            if (!mUsbManager.hasPermission(mAccessory)) {
                requestUsbPermission();
            } else {
                openAccessory();
            }
        }
    }
    
    /**
     * Request USB permission from user.
     */
    private void requestUsbPermission() {
        PendingIntent permissionIntent = PendingIntent.getBroadcast(
            this, 
            0, 
            new Intent(ACTION_USB_PERMISSION), 
            PendingIntent.FLAG_IMMUTABLE
        );
        mUsbManager.requestPermission(mAccessory, permissionIntent);
    }
    
    /**
     * Open USB accessory connection with proper resource management.
     */
    private void openAccessory() {
        synchronized (mConnectionLock) {
            if (mIsDestroyed.get()) return;
            
            try {
                closeStreamsSilently();
                
                mFileDescriptor = mUsbManager.openAccessory(mAccessory);
                if (mFileDescriptor == null) {
                    Log.e(TAG, "Failed to open accessory: file descriptor is null");
                    runOnUiThread(() -> {
                        mStatusText.setText(R.string.usb_open_failed);
                        showToast(R.string.usb_open_failed);
                    });
                    return;
                }
                
                mInputStream = new FileInputStream(mFileDescriptor.getFileDescriptor());
                mOutputStream = new FileOutputStream(mFileDescriptor.getFileDescriptor());
                mIsConnected.set(true);
                
                Log.d(TAG, "USB accessory opened successfully");
                runOnUiThread(this::updateUI);
                
                // Start background thread for reading commands
                startReadThread();
                
            } catch (IOException e) {
                Log.e(TAG, "Failed to open USB accessory", e);
                closeAccessory();
                runOnUiThread(() -> {
                    mStatusText.setText(getString(R.string.usb_open_failed) + ": " + e.getMessage());
                    showToast(R.string.usb_open_failed);
                });
            }
        }
    }
    
    /**
     * Start background thread for reading from computer.
     */
    private void startReadThread() {
        if (mReadThread != null && mReadThread.isAlive()) {
            mReadThread.interrupt();
        }
        
        mReadThread = new Thread(this::readFromComputer, "USB-Read-Thread");
        mReadThread.setDaemon(true);
        mReadThread.start();
    }
    
    /**
     * Close USB accessory connection safely.
     */
    private void closeAccessory() {
        synchronized (mConnectionLock) {
            mIsConnected.set(false);
            mIsListening.set(false);
            
            // Interrupt read thread
            if (mReadThread != null) {
                mReadThread.interrupt();
                mReadThread = null;
            }
            
            closeStreamsSilently();
            
            runOnUiThread(this::updateUI);
        }
    }
    
    /**
     * Close all streams silently without throwing exceptions.
     */
    private void closeStreamsSilently() {
        if (mInputStream != null) {
            try {
                mInputStream.close();
            } catch (IOException e) {
                Log.w(TAG, "Error closing input stream", e);
            }
            mInputStream = null;
        }
        
        if (mOutputStream != null) {
            try {
                mOutputStream.close();
            } catch (IOException e) {
                Log.w(TAG, "Error closing output stream", e);
            }
            mOutputStream = null;
        }
        
        if (mFileDescriptor != null) {
            try {
                mFileDescriptor.close();
            } catch (IOException e) {
                Log.w(TAG, "Error closing file descriptor", e);
            }
            mFileDescriptor = null;
        }
    }
    
    /**
     * Toggle recording state.
     */
    private void toggleRecording() {
        if (!mIsConnected.get()) {
            showToast(R.string.usb_connect_first);
            return;
        }
        
        if (mIsListening.get()) {
            stopRecording();
        } else {
            startRecording();
        }
    }
    
    /**
     * Start voice recording.
     */
    private void startRecording() {
        if (mSpeechRecognizer == null || mIsDestroyed.get()) {
            showToast(R.string.voice_recognition_not_available);
            return;
        }
        
        try {
            mSpeechIntent.putExtra(RecognizerIntent.EXTRA_LANGUAGE, getPreferredLanguage());
            mSpeechRecognizer.startListening(mSpeechIntent);
            mIsListening.set(true);
            
            Log.d(TAG, "Started listening for speech");
            runOnUiThread(() -> {
                mRecordButton.setText(R.string.record_stop);
                mStatusText.setText(R.string.voice_listening);
                showToast(R.string.voice_listening);
            });
        } catch (Exception e) {
            Log.e(TAG, "Error starting speech recognition", e);
            mIsListening.set(false);
            runOnUiThread(() -> {
                mStatusText.setText(R.string.record_error);
                showToast(R.string.record_error);
            });
        }
    }
    
    /**
     * Stop voice recording.
     */
    private void stopRecording() {
        if (mSpeechRecognizer != null && mIsListening.get()) {
            try {
                mSpeechRecognizer.stopListening();
                mIsListening.set(false);
                
                Log.d(TAG, "Stopped listening for speech");
                runOnUiThread(() -> {
                    mRecordButton.setText(R.string.record_start);
                    mStatusText.setText(R.string.usb_connected);
                    showToast(R.string.record_stopped);
                });
            } catch (Exception e) {
                Log.e(TAG, "Error stopping speech recognition", e);
            }
        }
    }
    
    /**
     * Read commands from computer in background thread.
     */
    private void readFromComputer() {
        byte[] buffer = new byte[1024];
        
        while (!Thread.currentThread().isInterrupted() && mIsConnected.get()) {
            try {
                if (mInputStream == null) break;
                
                int bytes = mInputStream.read(buffer);
                if (bytes > 0) {
                    String command = new String(buffer, 0, bytes, StandardCharsets.UTF_8).trim();
                    Log.d(TAG, "Received command from computer: " + command);
                    
                    processCommand(command);
                }
            } catch (IOException e) {
                if (mIsConnected.get()) {
                    Log.e(TAG, "Error reading from computer", e);
                }
                break;
            } catch (Exception e) {
                Log.e(TAG, "Unexpected error in read thread", e);
            }
        }
        
        // Connection lost
        if (mIsConnected.get()) {
            Log.w(TAG, "Connection lost, closing accessory");
            closeAccessory();
        }
    }
    
    /**
     * Process commands received from computer.
     */
    private void processCommand(String command) {
        if (command == null || command.isEmpty()) return;
        
        switch (command.toUpperCase()) {
            case "STOP":
                runOnUiThread(this::stopRecording);
                break;
            case "START":
                runOnUiThread(this::startRecording);
                break;
            default:
                Log.d(TAG, "Unknown command: " + command);
        }
    }
    
    /**
     * Send text to computer via USB.
     */
    private void sendTextToComputer(String text) {
        if (text == null || text.isEmpty()) return;
        
        synchronized (mConnectionLock) {
            if (mOutputStream == null) {
                Log.w(TAG, "Cannot send text: output stream is null");
                return;
            }
            
            try {
                String message = text + "\n";
                mOutputStream.write(message.getBytes(StandardCharsets.UTF_8));
                mOutputStream.flush();
                Log.d(TAG, "Sent text to computer: " + text);
            } catch (IOException e) {
                Log.e(TAG, "Failed to send text to computer", e);
                runOnUiThread(() -> {
                    mStatusText.setText(R.string.usb_send_failed);
                    showToast(R.string.usb_communication_failed);
                });
                closeAccessory();
            }
        }
    }
    
    /**
     * Get preferred language based on system locale.
     */
    private String getPreferredLanguage() {
        String language = getResources().getConfiguration().locale.getLanguage();
        if ("zh".equals(language)) {
            return "zh-CN";
        } else if ("en".equals(language)) {
            return "en-US";
        }
        return "en-US";
    }
    
    /**
     * Update UI based on current state.
     */
    private void updateUI() {
        boolean connected = mIsConnected.get();
        boolean listening = mIsListening.get();
        
        mRecordButton.setEnabled(connected);
        mLanguageText.setVisibility(connected ? View.VISIBLE : View.GONE);
        
        if (connected) {
            mRecordButton.setText(listening ? R.string.record_stop : R.string.record_start);
            mStatusText.setText(listening ? R.string.voice_listening : R.string.usb_connected);
        } else {
            mRecordButton.setText(R.string.usb_connect_first);
            mStatusText.setText(R.string.usb_disconnected);
        }
    }
    
    /**
     * Show toast message on UI thread.
     */
    private void showToast(int resId) {
        if (!mIsDestroyed.get()) {
            Toast.makeText(this, resId, Toast.LENGTH_SHORT).show();
        }
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
        runOnUiThread(() -> mStatusText.setText(R.string.voice_processing));
    }
    
    @Override
    public void onError(int error) {
        Log.e(TAG, "Speech recognition error: " + error);
        mIsListening.set(false);
        
        String errorMessage = getErrorMessage(error);
        runOnUiThread(() -> {
            mStatusText.setText(getString(R.string.voice_error_unknown) + ": " + errorMessage);
            mRecordButton.setText(R.string.record_start);
        });
    }
    
    /**
     * Get human-readable error message for speech recognition errors.
     */
    private String getErrorMessage(int error) {
        switch (error) {
            case SpeechRecognizer.ERROR_NETWORK: return getString(R.string.voice_error_network);
            case SpeechRecognizer.ERROR_AUDIO: return getString(R.string.voice_error_audio);
            case SpeechRecognizer.ERROR_SERVER: return getString(R.string.voice_error_server);
            case SpeechRecognizer.ERROR_CLIENT: return getString(R.string.voice_error_client);
            case SpeechRecognizer.ERROR_SPEECH_TIMEOUT: return getString(R.string.voice_error_no_speech);
            case SpeechRecognizer.ERROR_NO_MATCH: return getString(R.string.voice_error_timeout);
            case SpeechRecognizer.ERROR_RECOGNIZER_BUSY: return getString(R.string.voice_error_max_matches);
            case SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS: return getString(R.string.voice_error_language);
            default: return getString(R.string.voice_error_unknown);
        }
    }
    
    @Override
    public void onResults(Bundle results) {
        ArrayList<String> matches = results.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION);
        if (matches != null && !matches.isEmpty()) {
            String recognizedText = matches.get(0);
            Log.d(TAG, "Recognized text: " + recognizedText);
            
            sendTextToComputer(recognizedText);
            
            runOnUiThread(() -> {
                mLanguageText.setText(getString(R.string.text_sent_prefix) + recognizedText);
                showToast(R.string.text_sent);
            });
        }
        mIsListening.set(false);
        updateUI();
    }
    
    @Override
    public void onPartialResults(Bundle partialResults) {
        ArrayList<String> matches = partialResults.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION);
        if (matches != null && !matches.isEmpty()) {
            String partialText = matches.get(0);
            Log.d(TAG, "Partial text: " + partialText);
            runOnUiThread(() -> mLanguageText.setText(getString(R.string.text_partial_prefix) + partialText));
        }
    }
    
    @Override
    public void onEvent(int eventType, Bundle params) {
        // Handle custom events
    }
    
    @Override
    protected void onDestroy() {
        super.onDestroy();
        mIsDestroyed.set(true);
        
        // Stop speech recognizer
        if (mSpeechRecognizer != null) {
            try {
                mSpeechRecognizer.destroy();
            } catch (Exception e) {
                Log.w(TAG, "Error destroying speech recognizer", e);
            }
            mSpeechRecognizer = null;
        }
        
        closeAccessory();
    }
}
