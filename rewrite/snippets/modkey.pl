#!/usr/bin/perl

use strict;
use warnings;
use Foundation;

@NSEvent::ISA = qw(PerlObjCBridge);

NSBundle->bundleWithPath_('/System/Library/Frameworks/AppKit.framework')->load;

while (1) {
  warn NSEvent->modifierFlags
}


