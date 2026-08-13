package com.example

import android.content.Context
import android.content.res.XmlResourceParser
import androidx.test.core.app.ApplicationProvider
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.xmlpull.v1.XmlPullParser

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class NetworkSecurityConfigTest {

    private val context: Context = ApplicationProvider.getApplicationContext()

    @Test
    fun `network security config resource exists`() {
        val resId = context.resources.getIdentifier("network_security_config", "xml", context.packageName)
        assertTrue("network_security_config.xml resource not found", resId != 0)
    }

    @Test
    fun `network security config permits cleartext for emulator domains`() {
        val resId = context.resources.getIdentifier("network_security_config", "xml", context.packageName)
        val parser: XmlResourceParser = context.resources.getXml(resId)

        var eventType = parser.eventType
        val domains = mutableSetOf<String>()
        var currentPermitted: Boolean? = null

        while (eventType != XmlPullParser.END_DOCUMENT) {
            when (eventType) {
                XmlPullParser.START_TAG -> {
                    when (parser.name) {
                        "domain-config" -> {
                            currentPermitted = parser.getAttributeBooleanValue(null, "cleartextTrafficPermitted", false)
                        }
                        "domain" -> {
                            val domain = parser.getAttributeValue(null, "includeSubdomains")
                            val domainName = parser.nextText()
                            if (currentPermitted == true) {
                                domains.add(domainName)
                            }
                        }
                    }
                }
                XmlPullParser.END_TAG -> {
                    if (parser.name == "domain-config") {
                        currentPermitted = null
                    }
                }
            }
            eventType = parser.next()
        }

        assertTrue("10.0.2.2 should allow cleartext", domains.contains("10.0.2.2"))
        assertTrue("10.0.3.2 should allow cleartext", domains.contains("10.0.3.2"))
        assertTrue("127.0.0.1 should allow cleartext", domains.contains("127.0.0.1"))
    }
}
