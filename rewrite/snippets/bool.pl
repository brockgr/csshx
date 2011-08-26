#!/usr/bin/perl

use strict;
use warnings;
use Foundation;

@SBApplication::ISA = qw(PerlObjCBridge);
NSBundle->bundleWithPath_('/System/Library/Frameworks/ScriptingBridge.framework')->load;
my $terminal = SBApplication->applicationWithBundleIdentifier_("com.apple.terminal");
my $tab = $terminal->doScript_in_("exec sleep 10", undef);
warn $tab->selected;


