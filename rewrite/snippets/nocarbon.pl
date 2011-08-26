#!/usr/bin/perl

use strict;
use warnings;

use Foundation;

@NSScreen::ISA = @SBApplication::ISA = @NSColor::ISA = qw(PerlObjCBridge);

NSBundle->bundleWithPath_(
    '/System/Library/Frameworks/ScriptingBridge.framework' # Loads AppKit too
)->load;

my $terminal = SBApplication->applicationWithBundleIdentifier_(
    "com.apple.terminal"
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

    my $tab = $terminal->doScript_in_($cmd, undef);

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


package ObjCStruct;

my %heap; # Used to maintain references to temp perl data structures

sub Pointer  () { 'L!' }
sub CGFloat  () { (length pack('L!',0) == 4 ) ? 'f' : 'd' }
sub CGFloatS () { length(pack CGFloat,'0') }

sub unpack {
    my ($obj, $struct) = @_;
    my $int_ptr = ref($obj) ? $$obj : $$struct;
    my $pac_ptr = pack($obj->Pointer, $int_ptr);
    my $mem = unpack($obj->_ptr_pack_str, $pac_ptr);
    return unpack($obj->_mem_pack_str, $mem);
}

sub new {
    my ($pack, @vals) = @_;
    my $mem = pack($pack->_mem_pack_str, @vals);
    my $pac_ptr = pack($pack->_ptr_pack_str, $mem);
    my $int_ptr = CORE::unpack($pack->Pointer, $pac_ptr);
    $heap{$int_ptr} = $mem;
    bless my $obj = \$int_ptr, ref($pack) || $pack;
    return $obj;
}
    
sub DESTROY { delete $heap{${$_[0]}} }


package ObjCStruct::NSPoint;
# typedef struct _NSPoint { CGFloat x; CGFloat y; } NSPoint;
use base qw(ObjCStruct);
sub _mem_pack_str { $_[0]->CGFloat.'2' }
sub _ptr_pack_str { 'P'.$_[0]->CGFloatS*2 }

package ObjCStruct::NSSize;
# typedef struct _NSSize { CGFloat width; CGFloat height; } NSSize;
use base qw(ObjCStruct);
sub _mem_pack_str { $_[0]->CGFloat.'2' }
sub _ptr_pack_str { 'P'.$_[0]->CGFloatS*2 }

package ObjCStruct::NSRect;
# typedef struct _NSRect { NSPoint origin; NSSize size; } NSRect;
use base qw(ObjCStruct);
sub _mem_pack_str { $_[0]->CGFloat.'4' }
sub _ptr_pack_str { 'P'.$_[0]->CGFloatS*4 }


package main;


my $tty = open_window('exec','sleep','1');
my ($win, $tab) = window_by_tty($tty);

my $orig = ObjCStruct::NSPoint->new(100,100);
$win->setOrigin_($orig);

my $size = ObjCStruct::NSPoint->new(200,200);
$win->setSize_($size);

my $color = $tab->backgroundColor();
warn "Orig color = ".perlValue $color;
my $new_color = make_NSColor('{38036,0,0}');
