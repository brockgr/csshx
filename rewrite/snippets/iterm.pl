#!/usr/bin/perl

use strict;
use warnings;

use Foundation;

@NSScreen::ISA = @SBApplication::ISA = @NSColor::ISA =
@ITermTerminal::ISA =
qw(PerlObjCBridge);

NSBundle->bundleWithPath_(
    '/System/Library/Frameworks/ScriptingBridge.framework' # Loads AppKit too
)->load;

my $terminal = SBApplication->applicationWithBundleIdentifier_(
    "com.googlecode.iterm2"
);

sub perlValue { $_[0] && ${$_[0]} ? $_[0]->description()->UTF8String() : undef }

sub make_NSColor {
    my ($str) = @_;
    my ($r,$g,$b) = @_;
    if ($str =~ /^\{(\d+),(\d+),(\d+)\}$/) {
        ($r,$g,$b) = map { $_ / 65535 } ($1,$2,$3);
    } elsif ($str =~ /^#(\w\w)(\w\w)(\w\w)$/) {
        ($r,$g,$b) = map { hex($_) / 255 } ($1,$2,$3);
    } else {
        die "Bad color [$str]";
    }
    return NSColor->colorWithCalibratedRed_green_blue_alpha_($r,$g,$b,0);
}


sub window_by_tty {
    my $tty = $_[0];
    my $windows = $terminal->windows;
    my $tabs = $windows->valueForKey_("tabs");
    my $ttys = $windows->valueForKey_("tty");
    warn grep { $tty eq $_ } @{Foundation::perlRefFromObjectRef $windows->valueForKey_("tty")};
        
    for (my $n=0; $n<$ttys->count; $n++) {
        my $tty = $ttys->objectAtIndex_($n);
        warn "$n ".$tty->UTF8String;
    }

    
    for (my $n=0; $n<$windows->count; $n++) {
        my $window = $windows->objectAtIndex_($n);
        my $tabs = $window->tabs;
        for (my $m=0; $m<$tabs->count; $m++) {
            my $tab = $tabs->objectAtIndex_($m);
            warn "Window:".$window->id." Tab:$n\n";
            return ($window,$tab) if $tab->tty->UTF8String eq $tty;
        }
    }
    return;
}

sub open_window {
    my (@args) = @_;

    # Quote the command arguements
    my $cmd = join ' ', map { s/(["'])/\$1/g; "'$_'" } @args;

    #my $tab = $terminal->doScript_in_($cmd, undef);
#warn $terminal->class->UTF8String;
    #my $term = $terminal->makeTerminal;
    ##my $term = $terminal->initWithProperties(ITermTerminal);
#my $term = $terminal->classForScriptingClass_('TermTerminal');
use Data::Dumper qw(Dumper);
#my $term = Dumper Foundation::perlRefFromObjectRef $terminal->classesForScriptingNames;

my $win = $terminal->classForScriptingClass_('terminal')->alloc->init;
warn $terminal->currentTerminal;
my $a = $terminal->terminals->addObject_($win);
my $tab = $terminal->classForScriptingClass_('session')->alloc->init;
$win->sessions->addObject_($tab);
$tab->execCommand_('bash -c "ls; sleep 5"');
die $tab;
die;

    warn $tab->description->UTF8String;
    warn $tab->qualifiedSpecifier->description->UTF8String;
    my $tab_ev_desc = $tab->qualifiedSpecifier;
    my $tab_id  =  $tab_ev_desc->descriptorForKeyword_(unpack('N','seld'))->stringValue->UTF8String;
    my $win_ev_desc = $tab_ev_desc->descriptorForKeyword_(unpack('N','from'));
    my $window_id = $win_ev_desc->descriptorForKeyword_(unpack('N','seld'))->stringValue->UTF8String;

    print "Window:$window_id Tab:$tab_id\n";

    my $tty = $tab->tty->UTF8String;

    return $tty;
}


package main;


my $tty = open_window('exec','sleep','1');
my ($win, $tab) = window_by_tty($tty);
