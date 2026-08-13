package com.example

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import com.example.data.repository.DatabaseProvider
import com.example.ui.QuantLabApp
import com.example.ui.theme.QuantLabTheme

class MainActivity : ComponentActivity() {
  override fun onCreate(savedInstanceState: Bundle?) {
    super.onCreate(savedInstanceState)
    DatabaseProvider.init(this)
    enableEdgeToEdge()
    setContent {
      QuantLabTheme {
        QuantLabApp()
      }
    }
  }
}

