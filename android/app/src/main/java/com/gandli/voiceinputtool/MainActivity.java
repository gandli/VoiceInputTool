package com.gandli.voiceinputtool;

import android.app.Activity;
import android.app.PendingIntent;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.hardware.usb.UsbAccessory;
import android.hardware.usb.UsbManager;
import android.os.Bundle;
import android.os.ParcelFileDescriptor;
import android.speech.RecognizerIntent;
import android.util.Log;
import android.widget.Button;
import android.widget.TextView;
import android.widget.Toast;

import java.io.Closeable;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * Main activity for Voice Input Tool.
 * Manages USB accessory connection and voice recognition.
 */
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
    private volatile boolean mIsConnected = false;

    private final ExecutorService mExecutorService = Executors.newSingleThreadExecutor();
    private final Object mConnectionLock = new Object();

    /**
     * Broadcast receiver for USB permission and detachment events.
     */
    private final BroadcastReceiver mUsbReceiver = new BroadcastReceiver() {
        @Override
        public void onReceive(Context context, Intent intent) {
            String action = intent.getAction();
            if (action == null) return;

            switch (action) {
                case ACTION_USB_PERMISSION:
                    synchronized (mConnectionLock) {
                        UsbAccessory accessory = intent.getParcelableExtra(UsbManager.EXTRA_ACCESSORY);
                        if (intent.getBooleanExtra(UsbManager.EXTRA_PERMISSION_GRANTED, false)) {
                            if (accessory != null) {
                                mAccessory = accessory;
                                openAccessory();
                            }
                        } else {
                            Log.w(TAG, "USB permission denied");
                            showToast(R.string.usb_permission_denied);
                        }
                    }
                    break;

                case UsbManager.ACTION_USB_ACCESSORY_DETACHED:
                    synchronized (mConnectionLock) {
                        UsbAccessory detachedAccessory = intent.getParcelableExtra(UsbManager.EXTRA_ACCESSORY);
                        if (detachedAccessory != null && detachedAccessory.equals(mAccessory)) {
                            Log.d(TAG, "USB accessory detached");
                            closeAccessory();
                        }
                    }
                    break;
            }
        }
    };

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        initViews();
        initUsbManager();
        registerUsbReceiver();
        checkUsbAccessory();
        updateUI();
    }

    /**
     * Initialize UI views and set up click listeners.
     */
    private void initViews() {
        mRecordButton = findViewById(R.id.record_button);
        mStatusText = findViewById(R.id.status_text);
        mRecordButton.setOnClickListener(v -> startVoiceRecognition());
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
     * Register USB broadcast receiver for permission and detachment events.
     */
    private void registerUsbReceiver() {
        IntentFilter filter = new IntentFilter();
        filter.addAction(ACTION_USB_PERMISSION);
        filter.addAction(UsbManager.ACTION_USB_ACCESSORY_DETACHED);
        registerReceiver(mUsbReceiver, filter);
    }

    /**
     * Check if USB accessory is already connected.
     */
    private void checkUsbAccessory() {
        if (mUsbManager == null) return;

        UsbAccessory[] accessories = mUsbManager.getAccessoryList();
        if (accessories != null && accessories.length > 0) {
            mAccessory = accessories[0];
            requestUsbPermission();
        }
    }

    /**
     * Request permission for USB accessory.
     */
    private void requestUsbPermission() {
        if (mUsbManager.hasPermission(mAccessory)) {
            openAccessory();
        } else {
            PendingIntent permissionIntent = PendingIntent.getBroadcast(
                    this,
                    0,
                    new Intent(ACTION_USB_PERMISSION),
                    PendingIntent.FLAG_IMMUTABLE
            );
            mUsbManager.requestPermission(mAccessory, permissionIntent);
        }
    }

    /**
     * Open USB accessory connection.
     */
    private void openAccessory() {
        mExecutorService.execute(() -> {
            synchronized (mConnectionLock) {
                try {
                    closeStreamsSilently();

                    mFileDescriptor = mUsbManager.openAccessory(mAccessory);
                    if (mFileDescriptor != null) {
                        mInputStream = new FileInputStream(mFileDescriptor.getFileDescriptor());
                        mOutputStream = new FileOutputStream(mFileDescriptor.getFileDescriptor());
                        mIsConnected = true;
                        Log.d(TAG, "USB accessory opened successfully");
                        runOnUiThread(this::updateUI);
                    } else {
                        Log.e(TAG, "Failed to open accessory: file descriptor is null");
                    }
                } catch (IOException e) {
                    Log.e(TAG, "Failed to open USB accessory", e);
                    closeAccessory();
                }
            }
        });
    }

    /**
     * Close USB accessory connection safely.
     */
    private void closeAccessory() {
        synchronized (mConnectionLock) {
            mIsConnected = false;
            closeStreamsSilently();
            runOnUiThread(this::updateUI);
        }
    }

    /**
     * Close all streams silently without throwing exceptions.
     */
    private void closeStreamsSilently() {
        closeQuietly(mInputStream);
        closeQuietly(mOutputStream);
        closeQuietly(mFileDescriptor);

        mInputStream = null;
        mOutputStream = null;
        mFileDescriptor = null;
    }

    /**
     * Close a Closeable resource quietly.
     *
     * @param closeable the resource to close
     */
    private void closeQuietly(Closeable closeable) {
        if (closeable != null) {
            try {
                closeable.close();
            } catch (IOException e) {
                Log.w(TAG, "Error closing resource", e);
            }
        }
    }

    /**
     * Start voice recognition activity.
     */
    private void startVoiceRecognition() {
        if (!mIsConnected) {
            showToast(R.string.connect_first);
            return;
        }

        Intent intent = new Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH);
        intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM);
        intent.putExtra(RecognizerIntent.EXTRA_PROMPT, getString(R.string.speak_now));

        try {
            startActivityForResult(intent, REQUEST_VOICE_RECOGNITION);
        } catch (Exception e) {
            Log.e(TAG, "Voice recognition not available", e);
            showToast(R.string.voice_recognition_not_available);
        }
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);

        if (requestCode == REQUEST_VOICE_RECOGNITION) {
            handleVoiceRecognitionResult(resultCode, data);
        }
    }

    /**
     * Handle voice recognition result.
     *
     * @param resultCode the result code
     * @param data       the result data
     */
    private void handleVoiceRecognitionResult(int resultCode, Intent data) {
        if (resultCode == RESULT_OK && data != null) {
            ArrayList<String> results = data.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS);
            if (results != null && !results.isEmpty()) {
                String recognizedText = results.get(0);
                Log.d(TAG, "Recognized text: " + recognizedText);
                sendTextToComputer(recognizedText);
                updateStatusText(getString(R.string.sent_prefix) + recognizedText);
                showToast(R.string.text_sent);
            }
        } else {
            updateStatusText(getString(R.string.recognition_failed));
            showToast(R.string.recognition_failed);
        }
    }

    /**
     * Send text to computer via USB.
     *
     * @param text the text to send
     */
    private void sendTextToComputer(String text) {
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
                updateStatusText(getString(R.string.usb_send_failed));
                showToast(R.string.usb_communication_failed);
                closeAccessory();
            }
        }
    }

    /**
     * Update UI based on connection state.
     */
    private void updateUI() {
        if (mIsConnected) {
            mRecordButton.setEnabled(true);
            mStatusText.setText(R.string.connected_to_computer);
            mRecordButton.setText(R.string.start_voice_input);
        } else {
            mRecordButton.setEnabled(false);
            mStatusText.setText(R.string.not_connected);
            mRecordButton.setText(R.string.connect_first);
        }
    }

    /**
     * Update status text on UI thread.
     *
     * @param text the text to display
     */
    private void updateStatusText(String text) {
        runOnUiThread(() -> mStatusText.setText(text));
    }

    /**
     * Show toast message on UI thread.
     *
     * @param resId the string resource ID
     */
    private void showToast(int resId) {
        runOnUiThread(() -> Toast.makeText(this, resId, Toast.LENGTH_SHORT).show());
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        unregisterReceiver(mUsbReceiver);
        closeAccessory();
        mExecutorService.shutdown();
    }
}
