#!/usr/bin/perl

use strict;
use warnings;

use Foundation;
use Data::Dumper;

sub script {
    my ($script) = @_;
warn "\n\n$script";
    my $as = NSAppleScript->alloc->initWithSource_($script);
    my $ev_desc = $as->executeAndReturnError_(undef);
    $as->release;
    return $ev_desc;
}

my $tab_ev_desc = script('tell application "Terminal" to get do script "exec sleep 1"');

warn $tab_ev_desc->description->UTF8String;
#my $p = $tab_ev_desc->aeDesc();
#my $ptr = pack('L!',$p);
#warn unpack "P100", $ptr;
#exit;
#my $foo =  $tab_ev_desc->paramDescriptorForKeyword_(unpack('N', 'seld'));
#warn "$foo";
#warn "$$foo";
#warn $foo->stringValue->UTF8String;
#exit;
my $tab_id      = $tab_ev_desc->descriptorForKeyword_(unpack('N','seld'))->stringValue->UTF8String;
my $win_ev_desc = $tab_ev_desc->descriptorForKeyword_(unpack('N','from'));
my $window_id   = $win_ev_desc->descriptorForKeyword_(unpack('N','seld'))->stringValue->UTF8String;
warn "tab $tab_id of window id $window_id\n";


my $size_ev_desc = script('tell application "Terminal" to get size of window id '.$window_id);
warn $size_ev_desc->description->UTF8String;
warn $size_ev_desc->numberOfItems();
warn $size_ev_desc->descriptorAtIndex_(1)->int32Value;
warn $size_ev_desc->descriptorAtIndex_(2)->int32Value;

my $vis_ev_desc = script('tell application "Terminal" to get visible of window id '.$window_id);
warn $vis_ev_desc->description->UTF8String;
warn $vis_ev_desc->booleanValue;



#warn $ev->stringValue;
#warn $ev->data;
#my $desc =  $ev->stringValue->UTF8String;;
#while ($desc =~ /(\w\w)/g) {
    #print pack "H2", $1;
#}
#warn $ev->stringValue->UTF8String;

