#!/usr/bin/perl

use strict;
use warnings;
use Foundation;

@SBApplication::ISA =
@NSEvent::ISA =
 qw(PerlObjCBridge);
NSBundle->bundleWithPath_('/System/Library/Frameworks/ScriptingBridge.framework')->load;
my $terminal = SBApplication->applicationWithBundleIdentifier_("com.apple.terminal");

while (1) {
warn NSEvent->modifierFlags
}


