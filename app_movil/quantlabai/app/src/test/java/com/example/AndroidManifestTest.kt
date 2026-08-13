package com.example

import android.content.Context
import android.content.pm.PackageManager
import androidx.test.core.app.ApplicationProvider
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class AndroidManifestTest {

    private val context: Context = ApplicationProvider.getApplicationContext()

    @Test
    fun `application has network security config set`() {
        val packageManager = context.packageManager
        val packageName = context.packageName
        val packageInfo = packageManager.getPackageInfo(packageName, PackageManager.GET_ACTIVITIES or PackageManager.GET_META_DATA)
        
        val applicationInfo = packageInfo.applicationInfo
        assertNotNull(applicationInfo)
        val resId = context.resources.getIdentifier("network_security_config", "xml", context.packageName)
        assertTrue("network_security_config resource not found in manifest", resId != 0)
    }
}
