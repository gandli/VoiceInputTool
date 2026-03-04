package com.gandli.voiceinputtool;

import android.app.Activity;
import android.content.SharedPreferences;
import android.os.Bundle;
import android.widget.ArrayAdapter;
import android.widget.Spinner;
import android.widget.Switch;
import android.widget.Button;
import android.view.View;
import java.util.Locale;

public class SettingsActivity extends Activity {
    
    private static final String PREFS_NAME = "VoiceInputToolPrefs";
    private static final String KEY_LANGUAGE = "language";
    private static final String KEY_MULTI_SPEAKER = "multi_speaker";
    private static final String KEY_AUTO_SEND = "auto_send";
    
    private Spinner languageSpinner;
    private Switch multiSpeakerSwitch;
    private Switch autoSendSwitch;
    private Button saveButton;
    
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_settings);
        
        initializeViews();
        loadPreferences();
        setupLanguageOptions();
        setupClickListeners();
    }
    
    private void initializeViews() {
        languageSpinner = findViewById(R.id.language_spinner);
        multiSpeakerSwitch = findViewById(R.id.multi_speaker_switch);
        autoSendSwitch = findViewById(R.id.auto_send_switch);
        saveButton = findViewById(R.id.save_button);
    }
    
    private void loadPreferences() {
        SharedPreferences prefs = getSharedPreferences(PREFS_NAME, MODE_PRIVATE);
        
        // Load language preference
        String savedLanguage = prefs.getString(KEY_LANGUAGE, Locale.getDefault().getLanguage());
        // This will be set after we populate the spinner
        
        // Load boolean preferences
        boolean multiSpeakerEnabled = prefs.getBoolean(KEY_MULTI_SPEAKER, false);
        boolean autoSendEnabled = prefs.getBoolean(KEY_AUTO_SEND, true);
        
        multiSpeakerSwitch.setChecked(multiSpeakerEnabled);
        autoSendSwitch.setChecked(autoSendEnabled);
    }
    
    private void setupLanguageOptions() {
        String[] languages = {
            "en", "zh", "es", "fr", "de", "ja", "ko", "ru", "ar", "pt"
        };
        
        String[] languageNames = {
            "English", "Chinese", "Spanish", "French", "German", 
            "Japanese", "Korean", "Russian", "Arabic", "Portuguese"
        };
        
        ArrayAdapter<String> adapter = new ArrayAdapter<>(this, 
            android.R.layout.simple_spinner_item, languageNames);
        adapter.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item);
        languageSpinner.setAdapter(adapter);
        
        // Set default selection to current language
        SharedPreferences prefs = getSharedPreferences(PREFS_NAME, MODE_PRIVATE);
        String savedLanguage = prefs.getString(KEY_LANGUAGE, Locale.getDefault().getLanguage());
        
        for (int i = 0; i < languages.length; i++) {
            if (languages[i].equals(savedLanguage)) {
                languageSpinner.setSelection(i);
                break;
            }
        }
    }
    
    private void setupClickListeners() {
        saveButton.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                savePreferences();
                finish();
            }
        });
    }
    
    private void savePreferences() {
        SharedPreferences prefs = getSharedPreferences(PREFS_NAME, MODE_PRIVATE);
        SharedPreferences.Editor editor = prefs.edit();
        
        // Save language preference
        String[] languages = {"en", "zh", "es", "fr", "de", "ja", "ko", "ru", "ar", "pt"};
        int selectedLanguageIndex = languageSpinner.getSelectedItemPosition();
        editor.putString(KEY_LANGUAGE, languages[selectedLanguageIndex]);
        
        // Save boolean preferences
        editor.putBoolean(KEY_MULTI_SPEAKER, multiSpeakerSwitch.isChecked());
        editor.putBoolean(KEY_AUTO_SEND, autoSendSwitch.isChecked());
        
        editor.apply();
    }
}