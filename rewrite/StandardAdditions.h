/*
 * StandardAdditions.h
 */

#import <AppKit/AppKit.h>
#import <ScriptingBridge/ScriptingBridge.h>


@class StandardAdditionsPOSIXFile, StandardAdditionsURL, StandardAdditionsInternetAddress, StandardAdditionsWebPage, StandardAdditionsApplication;

enum StandardAdditionsStic {
	StandardAdditionsSticStop = '\000\000\000\000' /* The Stop alert icon */,
	StandardAdditionsSticNote = '\000\000\000\000' /* The Note alert icon */,
	StandardAdditionsSticCaution = '\000\000\000\000' /* The Caution alert icon */
};
typedef enum StandardAdditionsStic StandardAdditionsStic;

enum StandardAdditionsEtpt {
	StandardAdditionsEtptIP = 'eipt' /* via Internet Protocol */,
	StandardAdditionsEtptAppleTalk = 'eatt' /* via AppleTalk */
};
typedef enum StandardAdditionsEtpt StandardAdditionsEtpt;

enum StandardAdditionsEssv {
	StandardAdditionsEssvWebServers = 'esvw',
	StandardAdditionsEssvFTPServers = 'esvf',
	StandardAdditionsEssvTelnetHosts = 'esvt',
	StandardAdditionsEssvFileServers = 'esva',
	StandardAdditionsEssvNewsServers = 'esvn',
	StandardAdditionsEssvDirectoryServices = 'esvd',
	StandardAdditionsEssvMediaServers = 'esvm',
	StandardAdditionsEssvRemoteApplications = 'esve'
};
typedef enum StandardAdditionsEssv StandardAdditionsEssv;

enum StandardAdditionsEAlT {
	StandardAdditionsEAlTCritical = 'criT',
	StandardAdditionsEAlTInformational = 'infA',
	StandardAdditionsEAlTWarning = 'warN'
};
typedef enum StandardAdditionsEAlT StandardAdditionsEAlT;

enum StandardAdditionsAppf {
	StandardAdditionsAppfCurrentApplication = 'agcp',
	StandardAdditionsAppfFrontmostApplication = 'egfp',
	StandardAdditionsAppfApplicationAppName = 'agcp',
	StandardAdditionsAppfMe = 'agcp',
	StandardAdditionsAppfIt = 'agcp'
};
typedef enum StandardAdditionsAppf StandardAdditionsAppf;

enum StandardAdditionsAfdr {
	StandardAdditionsAfdrApplicationSupport = 'asup' /* The Application Support folder */,
	StandardAdditionsAfdrApplicationsFolder = 'apps' /* The user's Applications folder */,
	StandardAdditionsAfdrDesktop = 'desk' /* The user's Desktop folder */,
	StandardAdditionsAfdrDesktopPicturesFolder = 'dtp\304' /* The Desktop Pictures folder */,
	StandardAdditionsAfdrDocumentsFolder = 'docs' /* The user's Documents folder */,
	StandardAdditionsAfdrDownloadsFolder = 'down' /* The user's Downloads folder */,
	StandardAdditionsAfdrFavoritesFolder = 'favs' /* The user's Favorites folder */,
	StandardAdditionsAfdrFolderActionScripts = 'fasf' /* The user's Folder Action Scripts folder */,
	StandardAdditionsAfdrFonts = 'font' /* The Fonts folder */,
	StandardAdditionsAfdrHelp = '\304hlp' /* The Help folder */,
	StandardAdditionsAfdrHomeFolder = 'cusr' /* The user's home folder */,
	StandardAdditionsAfdrInternetPlugins = '\304net' /* The Internet Plug-Ins folder */,
	StandardAdditionsAfdrKeychainFolder = 'kchn' /* The user's Keychains folder */,
	StandardAdditionsAfdrLibraryFolder = 'dlib' /* The Library folder */,
	StandardAdditionsAfdrModemScripts = '\304mod' /* The Modem Scripts folder */,
	StandardAdditionsAfdrMoviesFolder = 'mdoc' /* The user's Movies folder */,
	StandardAdditionsAfdrMusicFolder = '\265doc' /* The user's Music folder */,
	StandardAdditionsAfdrPicturesFolder = 'pdoc' /* The user's Pictures folder */,
	StandardAdditionsAfdrPreferences = 'pref' /* The user's Preferences folder */,
	StandardAdditionsAfdrPrinterDescriptions = 'ppdf' /* The Printer Descriptions folder */,
	StandardAdditionsAfdrPublicFolder = 'pubb' /* The user's Public folder */,
	StandardAdditionsAfdrScriptingAdditions = '\304scr' /* The Scripting Additions folder */,
	StandardAdditionsAfdrScriptsFolder = 'scr\304' /* The user's Scripts folder */,
	StandardAdditionsAfdrServicesFolder = 'svcs' /* The Services folder */,
	StandardAdditionsAfdrSharedDocuments = 'sdat' /* The shared Documents folder */,
	StandardAdditionsAfdrSharedLibraries = '\304lib' /* The CFMSupport folder */,
	StandardAdditionsAfdrSitesFolder = 'site' /* The user's Sites folder */,
	StandardAdditionsAfdrStartupDisk = 'boot' /* The startup disk */,
	StandardAdditionsAfdrStartupItems = 'empz' /* The StartupItems folder */,
	StandardAdditionsAfdrSystemFolder = 'macs' /* The System folder */,
	StandardAdditionsAfdrSystemPreferences = 'sprf' /* The PreferencePanes folder */,
	StandardAdditionsAfdrTemporaryItems = 'temp' /* The Temporary Items folder */,
	StandardAdditionsAfdrTrash = 'trsh' /* The user's Trash folder */,
	StandardAdditionsAfdrUsersFolder = 'usrs' /* The Users folder */,
	StandardAdditionsAfdrUtilitiesFolder = 'uti\304' /* The Utilities folder */,
	StandardAdditionsAfdrWorkflowsFolder = 'flow' /* The Workflows folder */,
	StandardAdditionsAfdrVoices = 'fvoc' /* The Voices folder */,
	StandardAdditionsAfdrAppleMenu = 'amnu' /* The Apple Menu Items folder */,
	StandardAdditionsAfdrControlPanels = 'ctrl' /* The Control Panels folder */,
	StandardAdditionsAfdrControlStripModules = 'sdev' /* The Control Strip Modules folder */,
	StandardAdditionsAfdrExtensions = 'extn' /* The Extensions folder */,
	StandardAdditionsAfdrLauncherItemsFolder = 'laun' /* The Launcher Items folder */,
	StandardAdditionsAfdrPrinterDrivers = '\304prd' /* The Printer Drivers folder */,
	StandardAdditionsAfdrPrintmonitor = 'prnt' /* The PrintMonitor Documents folder */,
	StandardAdditionsAfdrShutdownFolder = 'shdf' /* The Shutdown Items folder */,
	StandardAdditionsAfdrSpeakableItems = 'spki' /* The Speakable Items folder */,
	StandardAdditionsAfdrStationery = 'odst' /* The Stationery folder */
};
typedef enum StandardAdditionsAfdr StandardAdditionsAfdr;

enum StandardAdditionsAfdm {
	StandardAdditionsAfdmApplicationSupportFolder = 'asup' /* The Application Support folder */,
	StandardAdditionsAfdmCurrentUserFolder = 'cusr' /* The user's home folder */,
	StandardAdditionsAfdmDesktopFolder = 'desk' /* The user's Desktop folder */,
	StandardAdditionsAfdmFolderActionScriptsFolder = 'fasf' /* The user's Folder Action Scripts folder */,
	StandardAdditionsAfdmFontsFolder = 'font' /* The Fonts folder */,
	StandardAdditionsAfdmFrontmostApplication = 'egfp' /* The frontmost application */,
	StandardAdditionsAfdmHelpFolder = '\304hlp' /* The Help folder */,
	StandardAdditionsAfdmPlugins = '\304net' /* The Internet Plug-Ins folder */,
	StandardAdditionsAfdmInternetPluginsFolder = '\304net' /* The Internet Plug-Ins folder */,
	StandardAdditionsAfdmModemScriptsFolder = '\304mod' /* The Modem Scripts folder */,
	StandardAdditionsAfdmPreferencesFolder = 'pref' /* The user's Preferences folder */,
	StandardAdditionsAfdmPrinterDescriptionsFolder = 'ppdf' /* The Printer Descriptions folder */,
	StandardAdditionsAfdmScriptingAdditionsFolder = '\304scr' /* The Scripting Additions folder */,
	StandardAdditionsAfdmSharedDocumentsFolder = 'sdat' /* The shared Documents folder */,
	StandardAdditionsAfdmSharedLibrariesFolder = '\304lib' /* The Shared Libraries folder */,
	StandardAdditionsAfdmStartup = 'empz' /* The StartupItems folder */,
	StandardAdditionsAfdmStartupItemsFolder = 'empz' /* The StartupItems folder */,
	StandardAdditionsAfdmTemporaryItemsFolder = 'temp' /* The Temporary Items folder */,
	StandardAdditionsAfdmTrashFolder = 'trsh' /* The Trash folder */,
	StandardAdditionsAfdmVoicesFolder = 'fvoc' /* The Speech Voices folder */,
	StandardAdditionsAfdmAppleMenuItems = 'amnu' /* The Apple Menu Items folder */,
	StandardAdditionsAfdmAppleMenuItemsFolder = 'amnu' /* The Apple Menu Items folder */,
	StandardAdditionsAfdmControlPanelsFolder = 'ctrl' /* The Control Panels folder */,
	StandardAdditionsAfdmControlStripModulesFolder = 'sdev' /* The Control Strip Modules folder */,
	StandardAdditionsAfdmExtensionsFolder = 'extn' /* The Extensions folder */,
	StandardAdditionsAfdmPrinterDriversFolder = '\304prd' /* The Printer Drivers folder */,
	StandardAdditionsAfdmPrintmonitorFolder = 'prnt' /* The PrintMonitor Documents folder */,
	StandardAdditionsAfdmShutdownItems = 'shdf' /* The Shutdown Items folder */,
	StandardAdditionsAfdmShutdownItemsFolder = 'shdf' /* The Shutdown Items folder */,
	StandardAdditionsAfdmStationeryFolder = 'odst' /* The Stationery folder */,
	StandardAdditionsAfdmAtEaseApplications = 'apps' /* The At Ease Applications folder */,
	StandardAdditionsAfdmAtEaseApplicationsFolder = 'apps' /* The At Ease Applications folder */,
	StandardAdditionsAfdmAtEaseDocuments = 'docs' /* The At Ease Documents folder */,
	StandardAdditionsAfdmAtEaseDocumentsFolder = 'docs' /* The At Ease Documents folder */,
	StandardAdditionsAfdmEditors = 'oded' /* The OpenDoc Editors folder */,
	StandardAdditionsAfdmEditorsFolder = 'oded' /* The OpenDoc Editors folder */
};
typedef enum StandardAdditionsAfdm StandardAdditionsAfdm;

enum StandardAdditionsFldm {
	StandardAdditionsFldmSystemDomain = 'flds',
	StandardAdditionsFldmLocalDomain = 'fldl',
	StandardAdditionsFldmNetworkDomain = 'fldn',
	StandardAdditionsFldmUserDomain = 'fldu',
	StandardAdditionsFldmClassicDomain = 'fldc'
};
typedef enum StandardAdditionsFldm StandardAdditionsFldm;

enum StandardAdditionsRdwr {
	StandardAdditionsRdwrShort = 'shor' /* short integers */,
	StandardAdditionsRdwrEof = 'eof ' /* end of file */,
	StandardAdditionsRdwrBoolean = 'bool' /* Boolean. */
};
typedef enum StandardAdditionsRdwr StandardAdditionsRdwr;

enum StandardAdditionsSavo {
	StandardAdditionsSavoAsk = 'ask ' /* display save as dialog */,
	StandardAdditionsSavoYes = 'yes ' /* overwrite existing file */,
	StandardAdditionsSavoNo = 'no  ' /* don't overwrite existing file */
};
typedef enum StandardAdditionsSavo StandardAdditionsSavo;

enum StandardAdditionsOlie {
	StandardAdditionsOlieUp = 'rndU' /* round up */,
	StandardAdditionsOlieDown = 'rndD' /* round down */,
	StandardAdditionsOlieTowardZero = 'rndZ' /* round toward zero */,
	StandardAdditionsOlieToNearest = 'rndN' /* round to nearest */,
	StandardAdditionsOlieAsTaughtInSchool = 'rndS' /* round to nearest with .5 always rounding away from zero */
};
typedef enum StandardAdditionsOlie StandardAdditionsOlie;

enum StandardAdditionsEsch {
	StandardAdditionsEschHttpURL = 'http',
	StandardAdditionsEschSecureHttpURL = 'htps',
	StandardAdditionsEschFtpURL = 'ftp ',
	StandardAdditionsEschMailURL = 'mail',
	StandardAdditionsEschFileURLObsolete = 'file',
	StandardAdditionsEschGopherURL = 'gphr',
	StandardAdditionsEschTelnetURL = 'tlnt',
	StandardAdditionsEschNewsURL = 'news',
	StandardAdditionsEschSecureNewsURL = 'snws',
	StandardAdditionsEschNntpURL = 'nntp',
	StandardAdditionsEschMessageURL = 'mess',
	StandardAdditionsEschMailboxURL = 'mbox',
	StandardAdditionsEschMultiURL = 'mult',
	StandardAdditionsEschLaunchURL = 'laun',
	StandardAdditionsEschAfpURL = 'afp ',
	StandardAdditionsEschAppleTalkURL = 'at  ',
	StandardAdditionsEschRemoteApplicationURL = 'eppc',
	StandardAdditionsEschStreamingMultimediaURL = 'rtsp',
	StandardAdditionsEschNetworkFileSystemURL = 'unfs',
	StandardAdditionsEschMailboxAccessURL = 'imap',
	StandardAdditionsEschMailServerURL = 'upop',
	StandardAdditionsEschDirectoryServerURL = 'uldp',
	StandardAdditionsEschUnknownURL = 'url\?' /* ???? */
};
typedef enum StandardAdditionsEsch StandardAdditionsEsch;



/*
 * Miscellaneous Commands
 */

// A file object specified with a POSIX (slash)-style pathname.
@interface StandardAdditionsPOSIXFile : SBObject

@property (copy, readonly) NSString *POSIXPath;  // the POSIX (slash)-style path of a file or alias object


@end



/*
 * Internet Suite
 */

// A Uniform Resource Locator or Uniform Resource ID (URI)
@interface StandardAdditionsURL : SBObject

@property (copy) NSDictionary *properties;  // property that allows getting and setting of multiple properties
@property (copy, readonly) NSString *name;  // a name given to this URL, usually the name of the page it refers to
@property (readonly) StandardAdditionsEsch scheme;  // the access scheme
@property (copy, readonly) StandardAdditionsInternetAddress *host;  // the host specified by this URL
@property (copy, readonly) NSString *path;  // the location of the target on the host
@property (copy, readonly) NSString *userName;  // the user name by which to access this URL
@property (copy, readonly) NSString *password;  // the password by which to access this URL


@end

// An Internet or Intranet address for the TCP/IP protocol
@interface StandardAdditionsInternetAddress : SBObject

@property (copy) NSDictionary *properties;  // property that allows getting and setting of multiple properties
@property (copy) NSString *DNSForm;  // the Domain Name System form of the address (e.g. apple.com)
@property (copy) NSString *dottedDecimalForm;  // the dotted-decimal form of the address (e.g. 17.255.1.1)
@property NSInteger port;  // the port number of the requested TCP/IP service


@end

// A web page in HyperText Markup Language form
@interface StandardAdditionsWebPage : SBObject

@property (copy) NSDictionary *properties;  // property that allows getting and setting of multiple properties
@property (copy, readonly) NSString *name;  // the name of the web page
@property (copy, readonly) StandardAdditionsURL *URL;  // the universal resource locator for this page
@property (copy, readonly) NSString *textEncoding;  // the text encoding method used for this page


@end



/*
 * Standard Suite
 */

@interface StandardAdditionsApplication : SBApplication

- (void) beep:(NSInteger)x;  // Beep 1 or more times
- (id) chooseApplicationWithTitle:(NSString *)withTitle withPrompt:(NSString *)withPrompt multipleSelectionsAllowed:(BOOL)multipleSelectionsAllowed as:(id)as;  // Choose an application on this machine or the network
- (NSColor *) chooseColorDefaultColor:(NSColor *)defaultColor;  // Choose a color
- (NSURL *) chooseFileWithPrompt:(NSString *)withPrompt ofType:(NSArray *)ofType defaultLocation:(NSURL *)defaultLocation invisibles:(BOOL)invisibles multipleSelectionsAllowed:(BOOL)multipleSelectionsAllowed showingPackageContents:(BOOL)showingPackageContents;  // Choose a file on a disk or server
- (NSURL *) chooseFileNameWithPrompt:(NSString *)withPrompt defaultName:(NSString *)defaultName defaultLocation:(NSURL *)defaultLocation;  // Get a new file reference from the user, without creating the file
- (NSURL *) chooseFolderWithPrompt:(NSString *)withPrompt defaultLocation:(NSURL *)defaultLocation invisibles:(BOOL)invisibles multipleSelectionsAllowed:(BOOL)multipleSelectionsAllowed showingPackageContents:(BOOL)showingPackageContents;  // Choose a folder on a disk or server
- (NSArray *) chooseFromList:(NSArray *)x withTitle:(NSString *)withTitle withPrompt:(NSString *)withPrompt defaultItems:(NSArray *)defaultItems OKButtonName:(NSString *)OKButtonName cancelButtonName:(NSString *)cancelButtonName multipleSelectionsAllowed:(BOOL)multipleSelectionsAllowed emptySelectionAllowed:(BOOL)emptySelectionAllowed;  // Choose one or more items from a list
- (id) chooseRemoteApplicationWithTitle:(NSString *)withTitle withPrompt:(NSString *)withPrompt;  // Choose a running application on a remote machine or on this machine
- (StandardAdditionsURL *) chooseURLShowing:(NSArray *)showing editableURL:(BOOL)editableURL;  // Choose a service on the Internet
- (void) delay:(NSNumber *)x;  // Pause for a fixed amount of time
- (NSDictionary *) displayAlert:(NSString *)x message:(NSString *)message as:(StandardAdditionsEAlT)as buttons:(NSArray *)buttons defaultButton:(id)defaultButton cancelButton:(id)cancelButton givingUpAfter:(NSInteger)givingUpAfter;  // Display an alert
- (NSDictionary *) displayDialog:(NSString *)x defaultAnswer:(NSString *)defaultAnswer hiddenAnswer:(BOOL)hiddenAnswer buttons:(NSArray *)buttons defaultButton:(id)defaultButton cancelButton:(id)cancelButton withTitle:(NSString *)withTitle withIcon:(id)withIcon withIcon:(StandardAdditionsStic)withIcon withIcon:(NSURL *)withIcon givingUpAfter:(NSInteger)givingUpAfter;  // Display a dialog box, optionally requesting user input
- (void) say:(NSString *)x displaying:(NSString *)displaying using:(NSString *)using_ speakingRate:(NSNumber *)speakingRate pitch:(NSNumber *)pitch modulation:(NSNumber *)modulation volume:(NSNumber *)volume stoppingCurrentSpeech:(BOOL)stoppingCurrentSpeech waitingUntilCompletion:(BOOL)waitingUntilCompletion savingTo:(id)savingTo;  // Speak the given text
- (NSDictionary *) infoFor:(NSURL *)x size:(BOOL)size;  // Return information for a file or folder
- (NSArray *) listDisks;  // Return a list of the currently mounted volumes
- (NSArray *) listFolder:(NSURL *)x invisibles:(BOOL)invisibles;  // Return the contents of a specified folder
- (void) mountVolume:(NSString *)x onServer:(NSString *)onServer inAppleTalkZone:(NSString *)inAppleTalkZone asUserName:(NSString *)asUserName withPassword:(NSString *)withPassword;  // Mount the specified server volume
- (id) pathTo:(StandardAdditionsAppf)x as:(id)as;  // Return the full path to the specified application
- (NSURL *) pathTo:(StandardAdditionsAfdr)x from:(StandardAdditionsFldm)from as:(id)as folderCreation:(BOOL)folderCreation;  // Return the full path to the specified folder
- (NSURL *) pathToResource:(NSString *)x inBundle:(NSURL *)inBundle inDirectory:(NSString *)inDirectory;  // Return the full path to the specified resource
- (NSString *) ASCIICharacter:(NSInteger)x;  // Convert a number to a character
- (NSInteger) ASCIINumber:(NSString *)x;  // Convert a character to a number
- (NSString *) localizedString:(NSString *)x fromTable:(NSString *)fromTable inBundle:(NSURL *)inBundle;  // Return the localized string for the specified key
- (NSInteger) offsetOf:(NSString *)of in:(NSString *)in_;  // Find one piece of text inside another
- (NSString *) summarize:(id)x in:(NSInteger)in_;  // Summarize the specified text or text file
- (void) setTheClipboardTo:(id)x;  // Place data on an application’s clipboard. Use inside a ‘tell’ block and activate the application first
- (id) theClipboardAs:(id)as;  // Return the contents of an application’s clipboard.  Use in a ‘tell’ block after activating the application
- (NSArray *) clipboardInfoFor:(id)for_;  // Return information about the clipboard
- (NSInteger) openForAccess:(NSURL *)x writePermission:(BOOL)writePermission;  // Open a disk file for the read and write commands
- (void) closeAccess:(id)x;  // Close a file that was opened for access
- (id) read:(id)x from:(NSInteger)from for:(NSInteger)for_ to:(NSInteger)to before:(NSString *)before until:(NSString *)until usingDelimiter:(NSString *)usingDelimiter usingDelimiters:(NSArray *)usingDelimiters as:(id)as;  // Read data from a file that has been opened for access
- (void) write:(id)x to:(id)to startingAt:(NSInteger)startingAt for:(NSInteger)for_ as:(id)as;  // Write data to a file that was opened for access with write permission
- (NSInteger) getEof:(id)x;  // Return the length, in bytes, of a file
- (void) setEof:(id)x to:(NSInteger)to;  // Set the length, in bytes, of a file
- (id) loadScript:(NSURL *)x;  // Return a script object loaded from a specified file
- (void) storeScriptIn:(NSURL *)in_ replacing:(StandardAdditionsSavo)replacing;  // Store a script object into a file
- (id) runScript:(id)x withParameters:(NSArray *)withParameters in:(NSString *)in_;  // Run a specified script or script file
- (NSArray *) scriptingComponents;  // Return a list of all scripting components (e.g. AppleScript)
- (NSDate *) currentDate;  // Return the current date and time
- (NSString *) doShellScript:(NSString *)x as:(id)as administratorPrivileges:(BOOL)administratorPrivileges userName:(NSString *)userName password:(NSString *)password alteringLineEndings:(BOOL)alteringLineEndings;  // Execute a shell script using the ‘sh’ shell
- (NSDictionary *) getVolumeSettings;  // Get the sound output and input volume settings
- (NSNumber *) randomNumber:(NSNumber *)x from:(NSNumber *)from to:(NSNumber *)to withSeed:(NSInteger)withSeed;  // Generate a random number
- (NSInteger) round:(double)x rounding:(StandardAdditionsOlie)rounding;  // Round number to integer
- (void) setVolume:(NSNumber *)x outputVolume:(NSInteger)outputVolume inputVolume:(NSInteger)inputVolume alertVolume:(NSInteger)alertVolume outputMuted:(BOOL)outputMuted;  // Set the sound output and/or input volume
- (id) systemAttributeHas:(NSInteger)has;  // Test attributes of this computer
- (NSDictionary *) systemInfo;  // Get information about the system
- (NSInteger) timeToGMT;  // Return the difference between local time and GMT (Universal Time)
- (void) openingFolder:(NSURL *)x;  // Called after a folder has been opened into a window
- (void) closingFolderWindowFor:(NSURL *)x;  // Called after a folder window has been closed
- (void) movingFolderWindowFor:(NSURL *)x from:(id)from;  // Called after a folder window has been moved or resized
- (void) addingFolderItemsTo:(NSURL *)x afterReceiving:(NSArray *)afterReceiving;  // Called after new items have been added to a folder
- (void) removingFolderItemsFrom:(NSURL *)x afterLosing:(NSArray *)afterLosing;  // Called after items have been removed from a folder
- (void) openLocation:(NSString *)x errorReporting:(BOOL)errorReporting;  // Opens a URL with the appropriate program
- (StandardAdditionsWebPage *) handleCGIRequest:(NSString *)x searchingFor:(NSString *)searchingFor withPostedData:(NSString *)withPostedData ofContentType:(NSString *)ofContentType usingAccessMethod:(NSString *)usingAccessMethod fromAddress:(NSString *)fromAddress fromUser:(NSString *)fromUser usingPassword:(NSString *)usingPassword withUserInfo:(NSString *)withUserInfo fromServer:(NSString *)fromServer viaPort:(NSString *)viaPort executingBy:(NSString *)executingBy referredBy:(NSString *)referredBy fromBrowser:(NSString *)fromBrowser usingAction:(NSString *)usingAction ofActionType:(NSString *)ofActionType fromClientIPAddress:(NSString *)fromClientIPAddress withFullRequest:(NSString *)withFullRequest withConnectionID:(NSInteger)withConnectionID fromVirtualHost:(NSString *)fromVirtualHost;  // Sent to a script to process a Common Gateway Interface request

@end

