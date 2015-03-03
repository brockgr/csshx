
---

# NAME #

csshX - Cluster SSH tool using Mac OS X Terminal.app



---

# SYNOPSIS #

csshX [**--login** _username_] [**--config** _filename_] [\_[user@](.md)host1[:port]_[_[user@]host2[:port]_] .. ]_

csshX [**-h** | **-m** | **-v** ]



---

# DESCRIPTION #

**csshX** is a tool to allow simultaneous control of multiple ssh sessions. _host1_, _host2_, etc. are either remote hostnames or remote cluster names. **csshX** will attempt to create an ssh session to each remote host in separate Terminal.app windows. A _master_ window will also be created. All keyboard input in the master will be sent to all the _slave_ windows.

To specify the username for each host, the hostname can be prepended by _user@_. Similarly, appending _:port_ will set the port to ssh to.

You can also use hostname ranges, to specify many hosts.



---

# OPTIONS #

### **-l** _username_, **--login** _username_ ###
Remote user to authenticate as for all hosts. This is overridden by _user@_.
### **-c** _configfile_, **--config** _configfile_ ###
Alternative config file to use
### **-h**, **--help** ###
Quick summary of program usage
### **-m**, **--man** ###
Full program man page
### **-v**, **--version** ###
Displays the version of csshX
### **--screen** _number or range_ ###
Sets the screen(s) on which to display the terminals, if you have multiple monitors. If the argument is passed a number, that screen will be used.
If a range (of the format **1-2**) is passed, a rectangle that fits within those displays will be chosen. Particularly odd arrangements of windows, such as "L" shapes will probably not work.
Screens are numbered from 1.
### **--space** _number_ ###
Sets the space (if Spaces is enabled) on which to display the terminals.
Default: _0_ (current space)
### **-x**, **--tile\_x** _number_ ###
(csshX only) The number of columns to use when tiling windows.
### **-y**, **--tile\_y** _number_ ###
(csshX only) The number of rows to use when tiling windows. **tile\_x** will be used if both are specified.
### **--ssh** _ssh command_ ###
Change the command that is run. May be useful if you use an alternative ssh binary or some wrapper script to connect to hosts.
### **--ssh\_args** _ssh arguments_ ###
Sets a list of arguments to pass to the **ssh** binary when run. If there is more than one, they must be quoted or escaped to prevent **csshX** from interpreting them.
### **--remote\_command** _command to run_ ###
Sets the command to run on the remote system after authenticating. If the command contains spaces, it should be quoted or escaped.
To run different commands on different hosts, see the **--hosts** option.
### **--hosts** _hosts\_file_ ###
Load a file containing a list of hostnames to connect to and, optionally, commands to run on each host. A single dash **-** can be used to read hosts data from standard input, for example, through a pipe.
See HOSTS for the file format.
### **--session\_max** _number_ ###
Set the maximum number of ssh Terminal sessions that can be opened during a single csshX session. By default csshX will not open more than 256 sessions. You must set this to something really high to get around that. (default: 256)
Note that you will probably run out of Pseudo-TTYs before reaching 256 terminal windows.
### **--ping\_test**, **--ping** _number_ ###
To avoid opening connections to machines that are down, or not running sshd, this option will make csshX ping each host/port that is specified. This uses the Net::Ping module to perform a simple syn/ack check.
Use of this option is highly recommended when subnet ranges are used.
### **--ping\_timeout** _number_ ###
This sets the timeout used when the "ping\_test" feature is enabled.
Due to the implementation of Net::Ping syn/ack checks, this timeout applies once per destination port used. Also, if the number of hosts to ping is greater than the number of filehandles available pings will be batched, and the timeout will apply once per batch. You can set 'ulimit -n' to improve this performance.
The value is in seconds. (default: 2)
### **--sock** _sockfile_ ###
Sets the Unix domain socket filename to be used for interprocess communication. This may be set by the user in the launcher session, possibly for security reasons.
### **--sorthosts** ###
Sort the host windows, by hostname, before opening them.
### **--slave\_settings\_set**, **--sss** _string_ ###
Change the "settings set" for slave windows. See slave\_settings\_set below for an explanation of why you might do this.
### **--master\_settings\_set**, **--mss** _string_ ###
Change the "settings set" for master windows.
### **-i**, **--interleave** _number_ ###
(csshX only) Interleave the hosts that were passed in. Useful when multiple clusters are specified.
For instance, if clusterA and clusterB each have 3 hosts, running csshX -tile\_x 2 -interleave 3 clusterA clusterB
will display as clusterA1 clusterB1 clusterA2 clusterB2 clusterA3 clusterB3
as opposed to the default clusterA1 clusterA2 clusterA3 clusterB1 clusterB2 clusterB3
### **--debug** _number_ ###
Sets the debug level. Number is optional and will default to 1 if omitted.
Currently only one level of debug is supported. It will enable backtrace on fatal errors, and will keep terminal windows open after terminating (so you can see any errors).



---

# HOSTNAME RANGES #

If you have a lot of similarly named hosts, or wish to open all hosts in a subnet, hostname ranges will simplify things. However this also allows opening a crazy number of windows. To save you from yourself, **session\_max** will limit the number of hosts opened.

It is also recommended to enable **ping\_test** if only a few machines on a subnet are actually available.

### **Subnets** ###
You can specify subnets using two syntaxes:
```
    192.168.1.0/28
    192.168.1.0/255.255.255.240
```

This will also work with a hostname, assuming it resolves to a valid IP.
If the IP address is not the network address, only that IP and IPs above that address will be used (e.g. 192.168.0.14/28 will only use 2 IP addresses).
### **Ranges** ###
A range is declared in square brackets. Rules are separated by commas. Ranges use a minus-sign. Ranges can be numeric or alphabetic.
Some examples:
```
    hostname[0-10]
    192.168.0.[5-20]
    host-[prod,dev][a-f]
    192.168.[0,2-3].[1-2,3-5]
```

### **Repeating** ###
You can repeat a hostname by using '+' sign and a number.
For example:
```
    localhost+4
```

This will open four connections to localhost.



---

# WINDOW CONTROL #

The master window allows additional windows to be opened, control of input to be selected, and re-tiling. These are all accessed using **Ctrl-a** key combination.

(Ctrl-a can be changed to another code using the action\_key setting in your csshrc)

Use **Esc** to return to input mode.

### **Ctrl-a c** ###
Open a new terminal and connect to another host. Prompts for hostname. **Esc** cancels hostname input.
This does not accept cluster names, ranges or subnets. This might be added in the future.
### **Ctrl-a Ctrl-a** ###
Sends a Control a (\001) character to all enabled terminals.
### **Ctrl-a r** ###
Retiles all windows. Also unminimises, unhides and brings windows to front.
### **Ctrl-a g** ###
Increase the number of grid columns used for tiling windows
### **Ctrl-a G** ###
Decrease the number of grid columns used for tiling windows
### **Ctrl-a m** ###
Minimise all windows. (Use retile to restore)
### **Ctrl-a h** ###
Hide all windows. This is much faster than minimising since there is no animation. (Use retile to restore)
### **Ctrl-a Ctrl-h** ###
Hide all windows and minimise the master. This is a neat way to hide your csshX session without filling your dock with icons.
### **Ctrl-a x** ###
Close all windows and exit.
### **Ctrl-a t** ###
Toggle the enabled status of all windows.
### **Ctrl-a n** ###
Re-enable all windows for input.
### **Ctrl-a space** ###
Disable current terminal and enable next terminal. (Works when only one terminal is enabled - see below)
### **Ctrl-a e** ###
Enter window selection mode. In window selection mode the following keys are available:

### **Arrow keys**, **h**,**j**,**k**,**l** ###
Change window selection.
### **e** ###
Enable input for selected window.
### **d** ###
Disable input for selected window.
### **t** ###
Toggle enable mode for selected window.
### **o** ###
Disable all windows except for selected.
### **O** ###
Zoom selected window and disable all other windows. Use **Ctrl-a r** to unzoom (and retile) the window.
### **Esc** ###
Return to input mode.

### **Ctrl-a b** ###
Enter bounds moving and resizing mode. The master window will grow to cover the slave windows. You may then use the mouse to drag and resize the master window to cover the area you wish to use. You may drag the window across to other screens or spaces.
If you don't want to reach for the mouse, the **Arrow** keys (or **h**,**j**,**k**,**l**) can be used to move the window. Holding **Control** and the previous keys will resize it.
The following keys are also available:

### **Enter** ###
Accept newly selected bounds and resize slaves.
### **Esc** ###
Revert to previous bounds.
### **r** ###
Reset to default screen (or configuration file) bounds.
### **f** ###
Set bounds to fill screen.
### **p** ###
Print the bounds to the screen in a suitable format for pasting into your csshrc.

### **Ctrl-a s** ###
Enter send text mode. This allows you to send preset strings to all active windows.
Strings are:

### **h** ###
The **hostname** string, as passed to the ssh command. This excludes any **user@** and **:port** parts.
### **c** ###
The connection string containing **user@**, **hostname** and **:port** if they were specified.
### **i** ###
Send the unique "window id". Each window is assigned a unique number by the operating system. This might be useful if you need to applescript the windows.
### **s** ###
Send the unique "slave id". Each slave window is assigned a unique number. This might be useful if you have multiple windows on the same host.

### **Ctrl-a o** ###
Enter sort menu. This changes the window arrangement order.

### **h** ###
Sort by **hostname**
### **i** ###
Sort by "slave id". This will be the same as the order that hosts were specified on the command line. (ping\_test'ed hosts will not be in any order)



---

# CONFIGURATION FILES #

**csshX** accepts Cluster-SSH **clusters** and **csshrc** style configurations. Not all Cluster-SSH attributes are supported, and a few attributes have been added.


## CLUSTERS ##

The default clusters file is **/etc/clusters**. Additional files can be specified using the **extra\_cluster\_file** setting in any **csshrc** file.

The format is:

```
    cluster1 host1 host2
    cluster2 host3 host4
```

Hash '#' can be used for comments.


## HOSTS ##

There is no default hosts file. It may be specified on the command line using **--hosts** or the **hosts** setting in any **csshrc** file.

The format is:

```
    hostname  command to run
    hostname2 other command to run
```

The "command to run" is optional. Hostnames may contain user name, ports or ranges of names (see "HOSTNAME RANGES").

Multiple **hosts** files may be used at once.

Hash '#' can be used for comments.


## CSSHRC ##

The default csshrc files are **/etc/csshrc**, **~/.csshrc**. Additional files can be specified with the **--config** option on the command line.

Hash '#' can be used at any point in the file for comments.

Color specifications can be in two formats. Applescript format consists of three integer values in the form **{nnnnn,nnnnn,nnnnn}**, where nnnnn's are red, green and blue decimal values between 0 and 65535. Web style is **HHHHHH** where HH's are red, green and blue hex values between 00 and FF (note the leading # is not used to avoid confusion with comments).

### **clusters** ###
A list of clusters of hosts.
```
    clusters = cluster1 cluster2
    cluster1 = hostname1 hostname2
    cluster2 = hostname3 hostname4
```

For each cluster defined in clusters, an entry must exist with the host definitions for that cluster.
### **extra\_cluster\_file** ###
An additional **clusters** configuration file to include.
```
    extra_cluster_file = /tmp/extra_clusters
```

### **color\_master\_background** ###
(csshX only) The color for the background of the master window. Default: _{38036,0,0}_ (dark red)
### **color\_master\_foreground** ###
(csshX only) The color for the foreground font of the master window. Default: _{65535,65535,65535}_ (white)
### **color\_setbounds\_background** ###
(csshX only) The background color in bounds setting mode. Default: _{17990,35209,53456}_ (mid-blue)
### **color\_setbounds\_foreground** ###
(csshX only) The color of the foreground font in bounds setting mode. Default: Nothing
### **master\_height** ###
(csshX only) The height of the master window. Default: _87_ pixels
### **color\_disabled\_background** ###
(csshX) The background color for a disabled window. Default: Nothing
### **color\_disabled\_foreground** ###
(csshX only) The foreground font color for a disabled window. Default: _{37779,37779,37779}_ (mid-gray)
### **color\_selected\_background** ###
(csshX only) The background for a selected window in window selection mode. Default: _{17990,35209,53456}_ (mid-blue)
### **color\_selected\_foreground** ###
(csshX only) The foreground for a selected window in window selection mode. Default: Nothing
### **slave\_settings\_set** ###
(csshX only) Apply a terminal "settings set" to the slave window. Defaults to your default "settings set", and will then apply the color settings above.
This may be handy if you are annoyed by the beeping terminal "bell" (which can be a little weird if you hear it from many terminals at once). In Terminal.app preferences, you can clone your default settings and maybe replace Advanced -> Audible bell with Visual bell. Then, if you set **slave\_settings\_set** to the name of the cloned "settings set" you should have silent csshX slaves.
### **master\_settings\_set** ###
(csshX only) Apply a terminal "settings set" to the master window. Defaults to your default "settings set", and will then apply the color settings above.
### **tile\_x** ###
(csshX only) The number of columns to use when tiling windows. Default: _0_ (auto-tile)
### **tile\_y** ###
(csshX only) The number of rows to use when tiling windows. **tile\_x** will be used if both are specified. Default: _0_ (auto-tile)
### **screen\_bounds** ###
(csshX only) The bounding area of the screen to use for arranging the terminal windows. Default is the actual screen size. Format is:
```
    { origin_x, origin_y, width, height }
```

### **screen** ###
(csshX only) The screen number on which to draw the terminal windows. See --screen in OPTIONS
### **space** ###
(Currently not supported on 10.7 Lion)
(csshX only) The Space in which to draw the terminal windows. See --space in OPTIONS
### **ssh** ###
Command to be used instead of **ssh**. See --ssh in OPTIONS
### **ssh\_args** ###
Arguments to be passed when **ssh** is run. See --ssh\_args in OPTIONS
### **remote\_command** ###
Command to run on remoted machines. See --remote\_command in OPTIONS
### **hosts** ###
A file containing hosts to be connected to, and optionally commands The **hosts** line may be repeated to read multiple files. See --hosts in OPTIONS and HOSTS
### **session\_max** ###
Maximum sessions to open. See --session\_max in OPTIONS
### **ping\_test** ###
Ping each host before attempting to connect See --ping\_test in OPTIONS
### **ping\_timeout** ###
The timeout, in seconds, for the ping test. See --ping\_timeout in OPTIONS
### **action\_key** ###
Change the enable key code that triggers the master menu. Default is \001 (Ctrl-a). To change it to Ctrl-z for example, add the following line to your **.csshrc**
```
    action_key = \032
```

The number is the octal value of the position of the letter in the alphabet. z => 26 decimal => 32 octal.
### **no\_growl** ###
Disable the Growl support (see "GROWL SUPPORT" for more details).
### **debug** ###
The debug level to use. Defaults to 0. See --debug in OPTIONS



---

# GROWL SUPPORT #

If Growl is installed, certain events will trigger notifications. If you do not like these you can either disable them using the **no\_growl** setting in .csshrc, or fine tune the messages in the Growl Preference pane.

For full details of Growl, visit http://growl.info/.



---

# BUGS #

None known. Please submit any bugs you might encounter, or feature requests to http://code.google.com/p/csshx/issues/



---

# CREDITS #

This software is inspired by the X11 based Cluster-SSH project by Duncan Ferguson http://sourceforge.net/projects/clusterssh/.

The use of TIOCSTI to feed characters into the slave terminal's input buffer was copied from the "Perl Cookbook, 2nd Edition" page 482, by Tom Christiansen and Nathan Torkington.

A list of helpful people who have contributed patches to this project is included in the README.txt distributed with csshX.



---

# AUTHOR #

Gavin Brock <gbrock@cpan.org> http://brock-family.org/gavin

Project page http://code.google.com/p/csshx/



---

# COPYRIGHT AND LICENSE #

Copyright 2010 by Gavin Brock <gbrock@cpan.org>.

This program is free software; you may redistribute it and/or modify it under the same terms as Perl itself.



---

# SEE ALSO #

http://clusterssh.sourceforge.net/, ssh, Foundation perl


---


**Auto-generated from git csshX:**

```
csshX 0.74-2-gb10e018
Date:   Mon Sep 12 18:45:59 2011 +0900
```
