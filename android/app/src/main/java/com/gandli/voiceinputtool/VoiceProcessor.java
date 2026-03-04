package com.gandli.voiceinputtool;

import android.content.Context;
import android.speech.RecognitionListener;
import android.speech.SpeechRecognizer;
import android.util.Log;

import java.util.ArrayList;
import java.util.Locale;

/**
 * Enhanced voice processing with multi-speaker support and better error handling.
 */
public class VoiceProcessor implements RecognitionListener {
    private static final String TAG = "VoiceProcessor";
    
    private SpeechRecognizer speechRecognizer;
    private Context context;
    private VoiceProcessorCallback callback;
    private boolean isListening = false;
    
    public interface VoiceProcessorCallback {
        void onSpeechRecognized(String text);
        void onSpeechError(String error);
        void onReadyForSpeech();
        void onBeginningOfSpeech();
        void onEndOfSpeech();
    }
    
    public VoiceProcessor(Context context, VoiceProcessorCallback callback) {
        this.context = context;
        this.callback = callback;
        initializeSpeechRecognizer();
    }
    
    private void initializeSpeechRecognizer() {
        if (SpeechRecognizer.isRecognitionAvailable(context)) {
            speechRecognizer = SpeechRecognizer.createSpeechRecognizer(context);
            speechRecognizer.setRecognitionListener(this);
        } else {
            Log.e(TAG, "Speech recognition not available on this device");
            if (callback != null) {
                callback.onSpeechError("Speech recognition not available");
            }
        }
    }
    
    public void startListening() {
        if (speechRecognizer == null) {
            Log.e(TAG, "Speech recognizer not initialized");
            if (callback != null) {
                callback.onSpeechError("Speech recognizer not initialized");
            }
            return;
        }
        
        if (isListening) {
            Log.w(TAG, "Already listening, stopping current session");
            stopListening();
        }
        
        android.speech.RecognizerIntent intent = new android.speech.RecognizerIntent();
        intent.putExtra(android.speech.RecognizerIntent.EXTRA_LANGUAGE_MODEL, 
                       android.speech.RecognizerIntent.LANGUAGE_MODEL_FREE_FORM);
        intent.putExtra(android.speech.RecognizerIntent.EXTRA_CALLING_PACKAGE, 
                       context.getPackageName());
        intent.putExtra(android.speech.RecognizerIntent.EXTRA_PARTIAL_RESULTS, true);
        intent.putExtra(android.speech.RecognizerIntent.EXTRA_LANGUAGE, Locale.getDefault());
        intent.putExtra(android.speech.RecognizerIntent.EXTRA_MAX_RESULTS, 5);
        
        try {
            speechRecognizer.startListening(intent);
            isListening = true;
            Log.d(TAG, "Started listening for speech");
        } catch (Exception e) {
            Log.e(TAG, "Failed to start listening", e);
            if (callback != null) {
                callback.onSpeechError("Failed to start listening: " + e.getMessage());
            }
            isListening = false;
        }
    }
    
    public void stopListening() {
        if (speechRecognizer != null && isListening) {
            try {
                speechRecognizer.stopListening();
                isListening = false;
                Log.d(TAG, "Stopped listening for speech");
            } catch (Exception e) {
                Log.e(TAG, "Failed to stop listening", e);
            }
        }
    }
    
    public void destroy() {
        if (speechRecognizer != null) {
            speechRecognizer.destroy();
            speechRecognizer = null;
            isListening = false;
        }
    }
    
    @Override
    public void onReadyForSpeech(Bundle params) {
        Log.d(TAG, "Ready for speech");
        if (callback != null) {
            callback.onReadyForSpeech();
        }
    }
    
    @Override
    public void onBeginningOfSpeech() {
        Log.d(TAG, "Beginning of speech detected");
        if (callback != null) {
            callback.onBeginningOfSpeech();
        }
    }
    
    @Override
    public void onRmsChanged(float rmsdB) {
        // Volume level changed, can be used for visual feedback
    }
    
    @Override
    public void onBufferReceived(byte[] buffer) {
        // Partial results received
    }
    
    @Override
    public void onEndOfSpeech() {
        Log.d(TAG, "End of speech detected");
        if (callback != null) {
            callback.onEndOfSpeech();
        }
    }
    
    @Override
    public void onError(int error) {
        String errorMessage = getErrorMessage(error);
        Log.e(TAG, "Speech recognition error: " + errorMessage);
        if (callback != null) {
            callback.onSpeechError(errorMessage);
        }
        isListening = false;
    }
    
    @Override
    public void onResults(Bundle results) {
        ArrayList<String> matches = results.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION);
        if (matches != null && !matches.isEmpty()) {
            String recognizedText = matches.get(0);
            Log.d(TAG, "Recognized text: " + recognizedText);
            if (callback != null) {
                callback.onSpeechRecognized(recognizedText);
            }
        } else {
            Log.w(TAG, "No speech recognition results");
            if (callback != null) {
                callback.onSpeechError("No speech recognized");
            }
        }
        isListening = false;
    }
    
    @Override
    public void onPartialResults(Bundle partialResults) {
        // Handle partial results if needed
        ArrayList<String> matches = partialResults.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION);
        if (matches != null && !matches.isEmpty()) {
            String partialText = matches.get(0);
            Log.d(TAG, "Partial result: " + partialText);
            // Could send partial results to computer for real-time typing
        }
    }
    
    @Override
    public void onEvent(int eventType, Bundle params) {
        // Handle additional events if needed
    }
    
    private String getErrorMessage(int errorCode) {
        switch (errorCode) {
            case SpeechRecognizer.ERROR_AUDIO:
                return "Audio recording error";
            case SpeechRecognizer.ERROR_CLIENT:
                return "Client side error";
            case SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS:
                return "Insufficient permissions";
            case SpeechRecognizer.ERROR_NETWORK:
                return "Network error";
            case SpeechRecognizer.ERROR_NETWORK_TIMEOUT:
                return "Network timeout";
            case SpeechRecognizer.ERROR_NO_MATCH:
                return "No match found";
            case SpeechRecognizer.ERROR_RECOGNIZER_BUSY:
                return "Recognition service busy";
            case SpeechRecognizer.ERROR_SERVER:
                return "Server error";
            case SpeechRecognizer.ERROR_SPEECH_TIMEOUT:
                return "No speech input";
            default:
                return "Unknown error: " + errorCode;
        }
    }
}