#!/usr/bin/perl

use strict;
use warnings;

use Foundation;

NSBundle->bundleWithPath_( '/System/Library/Frameworks/AppKit.framework')->load;

my $regDict = Foundation::objectRefFromPerlRef({
    AllNotifications => [ 'Enable Window' ],
    ApplicationName  => 'csshX',
    NotificationName => 'Enable Window',
});

@NSWorkspace::ISA = qw(PerlObjCBridge);
my $path = NSWorkspace->sharedWorkspace->absolutePathForAppBundleWithIdentifier_('com.apple.terminal');
my $icon = NSWorkspace->sharedWorkspace->iconForFile_($path);
$regDict->setObject_forKey_($icon->TIFFRepresentation, 'ApplicationIcon');


NSDistributedNotificationCenter->defaultCenter->postNotificationName_object_userInfo_options_(
    'GrowlApplicationRegistrationNotification', undef, $regDict, 2
);

$regDict->setObject_forKey_('Test titel', 'NotificationTitle');

NSDistributedNotificationCenter->defaultCenter->postNotificationName_object_userInfo_options_(
    'GrowlNotification', undef, $regDict, 2
);
