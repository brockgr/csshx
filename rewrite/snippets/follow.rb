#!/usr/bin/ruby
require 'dl';
dl = DL::dlopen('/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices')
con = dl.sym("_CGSDefaultConnection", 'I').call()
ARGV.map! {|wid| Integer(wid)}
r,rs = dl.sym("CGSGetWindowWorkspace", 'IIIi').call(con[0], ARGV.shift, 0)
dl.sym("CGSMoveWorkspaceWindowList", 'IIAII').call(con[0], ARGV, ARGV.length, rs[2])
