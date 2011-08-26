/*
 * ITerm.h
 * sdef ~/Downloads/iTerm.app | sdp -fh --basename ITerm
 */

#import <AppKit/AppKit.h>
#import <ScriptingBridge/ScriptingBridge.h>


@class ITermItem, ITermITermApplication, ITermColor, ITermDocument, ITermWindow, ITermAttributeRun, ITermCharacter, ITermParagraph, ITermText, ITermAttachment, ITermWord, ITermSession, ITermTerminal, ITermPrintSettings;

enum ITermSavo {
	ITermSavoAsk = 'ask ' /* Ask the user whether or not to save the file. */,
	ITermSavoNo = 'no  ' /* Do not save the file. */,
	ITermSavoYes = 'yes ' /* Save the file. */
};
typedef enum ITermSavo ITermSavo;

enum ITermEnum {
	ITermEnumStandard = 'lwst' /* Standard PostScript error handling */,
	ITermEnumDetailed = 'lwdt' /* print a detailed report of PostScript errors */
};
typedef enum ITermEnum ITermEnum;



/*
 * Standard Suite
 */

// A scriptable object.
@interface ITermItem : SBObject

@property (copy) NSDictionary *properties;  // All of the object's properties.

- (void) closeSaving:(ITermSavo)saving savingIn:(NSURL *)savingIn;  // Close an object.
- (void) delete;  // Delete an object.
- (void) duplicateTo:(SBObject *)to withProperties:(NSDictionary *)withProperties;  // Copy object(s) and put the copies at a new location.
- (BOOL) exists;  // Verify if an object exists.
- (void) moveTo:(SBObject *)to;  // Move object(s) to a new location.
- (void) saveAs:(NSString *)as in:(NSURL *)in_;  // Save an object.
- (void) execCommand:(NSString *)command;  // Executes a command in a session (attach a trailing space for commands without carriage return)
- (void) launchSession:(NSString *)session;  // Launches a default or saved session
- (void) select;  // Selects a specified session
- (void) terminate;  // Terminates a session
- (void) writeContentsOfFile:(NSString *)contentsOfFile text:(NSString *)text;  // Writes text or file contents into a session

@end

// An application's top level scripting object.
@interface ITermITermApplication : SBApplication

- (SBElementArray *) documents;
- (SBElementArray *) windows;

@property (readonly) BOOL frontmost;  // Is this the frontmost (active) application?
@property (copy, readonly) NSString *name;  // The name of the application.
@property (copy, readonly) NSString *version;  // The version of the application.

- (ITermDocument *) open:(NSURL *)x;  // Open an object.
- (void) print:(NSURL *)x printDialog:(BOOL)printDialog withProperties:(ITermPrintSettings *)withProperties;  // Print an object.
- (void) quitSaving:(ITermSavo)saving;  // Quit an application.

@end

// A color.
@interface ITermColor : ITermItem


@end

// A document.
@interface ITermDocument : ITermItem

@property (readonly) BOOL modified;  // Has the document been modified since the last save?
@property (copy) NSString *name;  // The document's name.
@property (copy) NSString *path;  // The document's path.


@end

// A window.
@interface ITermWindow : ITermItem

@property NSRect bounds;  // The bounding rectangle of the window.
@property (readonly) BOOL closeable;  // Whether the window has a close box.
@property (copy, readonly) ITermDocument *document;  // The document whose contents are being displayed in the window.
@property (readonly) BOOL floating;  // Whether the window floats.
- (NSInteger) id;  // The unique identifier of the window.
@property NSInteger index;  // The index of the window, ordered front to back.
@property (readonly) BOOL miniaturizable;  // Whether the window can be miniaturized.
@property BOOL miniaturized;  // Whether the window is currently miniaturized.
@property (readonly) BOOL modal;  // Whether the window is the application's current modal window.
@property (copy) NSString *name;  // The full title of the window.
@property (readonly) BOOL resizable;  // Whether the window can be resized.
@property (readonly) BOOL titled;  // Whether the window has a title bar.
@property BOOL visible;  // Whether the window is currently visible.
@property (readonly) BOOL zoomable;  // Whether the window can be zoomed.
@property BOOL zoomed;  // Whether the window is currently zoomed.


@end



/*
 * Text Suite
 */

// This subdivides the text into chunks that all have the same attributes.
@interface ITermAttributeRun : ITermItem

- (SBElementArray *) attachments;
- (SBElementArray *) attributeRuns;
- (SBElementArray *) characters;
- (SBElementArray *) paragraphs;
- (SBElementArray *) words;

@property (copy) NSColor *color;  // The color of the first character.
@property (copy) NSString *font;  // The name of the font of the first character.
@property NSInteger size;  // The size in points of the first character.


@end

// This subdivides the text into characters.
@interface ITermCharacter : ITermItem

- (SBElementArray *) attachments;
- (SBElementArray *) attributeRuns;
- (SBElementArray *) characters;
- (SBElementArray *) paragraphs;
- (SBElementArray *) words;

@property (copy) NSColor *color;  // The color of the first character.
@property (copy) NSString *font;  // The name of the font of the first character.
@property NSInteger size;  // The size in points of the first character.


@end

// This subdivides the text into paragraphs.
@interface ITermParagraph : ITermItem

- (SBElementArray *) attachments;
- (SBElementArray *) attributeRuns;
- (SBElementArray *) characters;
- (SBElementArray *) paragraphs;
- (SBElementArray *) words;

@property (copy) NSColor *color;  // The color of the first character.
@property (copy) NSString *font;  // The name of the font of the first character.
@property NSInteger size;  // The size in points of the first character.


@end

// Rich (styled) text
@interface ITermText : ITermItem

- (SBElementArray *) attachments;
- (SBElementArray *) attributeRuns;
- (SBElementArray *) characters;
- (SBElementArray *) paragraphs;
- (SBElementArray *) words;

@property (copy) NSColor *color;  // The color of the first character.
@property (copy) NSString *font;  // The name of the font of the first character.
@property NSInteger size;  // The size in points of the first character.


@end

// Represents an inline text attachment.  This class is used mainly for make commands.
@interface ITermAttachment : ITermText

@property (copy) NSString *fileName;  // The path to the file for the attachment


@end

// This subdivides the text into words.
@interface ITermWord : ITermItem

- (SBElementArray *) attachments;
- (SBElementArray *) attributeRuns;
- (SBElementArray *) characters;
- (SBElementArray *) paragraphs;
- (SBElementArray *) words;

@property (copy) NSColor *color;  // The color of the first character.
@property (copy) NSString *font;  // The name of the font of the first character.
@property NSInteger size;  // The size in points of the first character.


@end



/*
 * iTerm Suite
 */

// Main application class
@interface ITermITermApplication (ITermSuite)

- (SBElementArray *) terminals;

@property (copy) ITermTerminal *currentTerminal;  // currently active terminal

@end

// A terminal session
@interface ITermSession : ITermItem

@property (copy) NSColor *backgroundColor;  // Background color
@property (copy) NSString *backgroundImagePath;  // Path to background image
@property (copy) NSColor *boldColor;  // Bold color
@property (copy, readonly) NSString *contents;  // text of the session
@property (copy) NSColor *cursorColor;  // Cursor color
@property (copy) NSColor *cursor_textColor;  // Cursor text color
@property (copy) NSColor *foregroundColor;  // Foreground color
- (NSString *) id;  // id of session; set to tty name
@property (copy) NSString *name;  // Name of this session
@property NSInteger number;  // index of session
@property (copy) NSColor *selectedTextColor;  // Selected text color
@property (copy) NSColor *selectionColor;  // Selection color
@property double transparency;  // Transparency (0-1)
@property (copy, readonly) NSString *tty;  // tty device of session


@end

// A pseudo terminal
@interface ITermTerminal : ITermItem

- (SBElementArray *) sessions;

@property BOOL antiAlias;  // Anti alias for window
@property (copy) ITermSession *currentSession;  // current session in the terminal
@property NSInteger numberOfColumns;  // Number of columns
@property NSInteger numberOfRows;  // Number of rows


@end



/*
 * Type Definitions
 */

@interface ITermPrintSettings : SBObject

@property NSInteger copies;  // the number of copies of a document to be printed
@property BOOL collating;  // Should printed copies be collated?
@property NSInteger startingPage;  // the first page of the document to be printed
@property NSInteger endingPage;  // the last page of the document to be printed
@property NSInteger pagesAcross;  // number of logical pages laid across a physical page
@property NSInteger pagesDown;  // number of logical pages laid out down a physical page
@property (copy) NSDate *requestedPrintTime;  // the time at which the desktop printer should print the document
@property ITermEnum errorHandling;  // how errors are handled
@property (copy) NSString *faxNumber;  // for fax number
@property (copy) NSString *targetPrinter;  // for target printer

- (void) closeSaving:(ITermSavo)saving savingIn:(NSURL *)savingIn;  // Close an object.
- (void) delete;  // Delete an object.
- (void) duplicateTo:(SBObject *)to withProperties:(NSDictionary *)withProperties;  // Copy object(s) and put the copies at a new location.
- (BOOL) exists;  // Verify if an object exists.
- (void) moveTo:(SBObject *)to;  // Move object(s) to a new location.
- (void) saveAs:(NSString *)as in:(NSURL *)in_;  // Save an object.
- (void) execCommand:(NSString *)command;  // Executes a command in a session (attach a trailing space for commands without carriage return)
- (void) launchSession:(NSString *)session;  // Launches a default or saved session
- (void) select;  // Selects a specified session
- (void) terminate;  // Terminates a session
- (void) writeContentsOfFile:(NSString *)contentsOfFile text:(NSString *)text;  // Writes text or file contents into a session

@end

