#!/usr/bin/ruby

require 'dl';

wid = 91080
space = 2;


dl = DL::dlopen('/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices')
print "#{dl}\n"

_CGSDefaultConnection = dl.sym("_CGSDefaultConnection", 'I');
print "#{_CGSDefaultConnection}\n"

foo = dl.sym("CGSMoveWorkspaceWindowList", 'IIiII');
print "#{foo}\n"

con = _CGSDefaultConnection.call();
print "#{con}\n"

foo.call(con[0], wid, 1, space);
