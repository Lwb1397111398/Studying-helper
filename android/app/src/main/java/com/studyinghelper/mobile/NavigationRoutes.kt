package com.studyinghelper.mobile

import android.net.Uri

fun routeParam(value: String): String = Uri.encode(value)
