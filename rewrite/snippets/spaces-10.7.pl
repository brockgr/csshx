#!/usr/bin/perl

use strict;
use warnings;
use Foundation;

@SBApplication::ISA = qw(PerlObjCBridge);
NSBundle->bundleWithPath_('/System/Library/Frameworks/ScriptingBridge.framework')->load;


# http://stackoverflow.com/questions/6768684/osx-lion-applescript-how-to-get-current-space-from-mission-control
# Get the UUID by index - but now what?

my $index = 1;

my $defs = NSUserDefaults->alloc->init;
$defs->addSuiteNamed_("com.apple.spaces");
my $arr = $defs->arrayForKey_("spaces");
my $dict = $arr->objectAtIndex_($index);
warn $dict->description->UTF8String;
my $uuid = $dict->objectForKey_("uuid")->UTF8String;
warn $uuid;
