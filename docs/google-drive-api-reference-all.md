# Google Drive API v3 Reference — Consolidated Local Copy

Generated from public Google Workspace Drive API documentation.

Pages included: 131

---

# Drive UI integration overview Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/guides/about-apps

- Home
- Google Workspace
- Google Drive
- Guides
The
Google Drive user interface
(UI)
is a
Google-provided application where Drive users can create,
organize, discover, and share content stored on Google Drive. You can
integrate your Drive-enabled app with the Drive UI
to take advantage of these features. There are two integrations that you can
perform:

- Using the
Drive UI's "New" button
.
- Using the
Drive UI's "Open with" menu item
.

## Drive UI's "New" button

If you want Drive UI users to call your app to create a file,
integrate your app with the Drive UI's "New" button.

The "New" button lets users open your application or other editor-style apps,
such as Google Docs and Google Sheets, to create a new document.


## Drive UI's "Open with" menu item

If you want Drive UI users to open documents with your app,
integrate your app with the Drive UI's "Open with" menu item.

When a user right-clicks on a file in the Drive UI, a context
menu opens. The right-click menu contains an "Open with" item letting the user
select an application to open the file.


## Related topics

For instructions on how to begin your integration, continue to
Configure a
Drive UI integration
.

Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2026-04-20 UTC.


---

# Identify which change log to track Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/guides/about-changelogs

- Home
- Google Workspace
- Google Drive
- Guides
The user and shared drive change logs are defined in the
Changes and revisions overview
. This guide provides more information about individual change log entries and tips for when to track changes in either the user change log or the shared drive change log.


## Change entry after file moves to a shared drive

After a file is moved to a shared drive, that shared drive change log continues logging changes for that file, not the user change log. You should then query the shared drive change log to detect new changes to that item.


## Change entry for individual items in a shared drive

If a non-member is granted file access to individual items in a shared drive,
changes to those items are tracked in the user change log, not the shared drive change log. This behavior is the same as non-shared drive items that are shared directly with users.


## Change entry for lost access permission

If a user loses access permission to a file, the change log entry will say
deleted
.
However, the file is still available to other users who still have permission to access the file. If the item is deleted for all users, it will get marked
deleted
in all user change logs.

When a file moves between user corpora it may also appear
deleted
even though the user still retains access to the file. If you query change logs for multiple corpora, use the
includeCorpusRemovals
parameter in
Changes.list
to disambiguate corpus moves from loss of access.
For definitions of different corpora, see
Files and folders overview
.

Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2026-04-23 UTC.


---

# Track changes for users and shared drives Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/guides/about-changes

- Home
- Google Workspace
- Google Drive
- Guides
For Google Drive apps that need to keep track of changes to items in Drive, the
Changes collection
provides an efficient way to
detect changes. The collection works by providing the current state of each
item, if and only if the item has changed since a given point in time.

Google Drive keeps a change log for each user and shared drive. Each has
their own record of changes to items that are of interest to them.

To track changes for
all
items visible to a user, both the user change log and the
change logs for all shared drives the user is a member of need to be replayed.


## Enable change entries

A change entry represents the state of the file or shared drive at a given point
in time. A change does not provide a delta between revisions. Applications
that need to know which properties have changed should persist the
previously known state of the item and compare.

Since changes represent the current state of an item, individual change
entries may be invalidated and replaced with a newer change entry for
the corresponding item.


## Tombstones

Change entries for items no longer available to a user are marked as
deleted
in the change entry. Only the ID of the item is available in the change entry.


## Track shared drives

Each shared drive has its own change log. Even though a user may be a member
of a shared drive, certain changes are only reflected in the shared drive change
log and never in the user’s change log. If a file belongs to a shared drive,
even if the file still appeared on the user’s change log at some point in the
past, replaying the user’s change log alone won't correctly update the file's
status. Instead you must replay the shared drive’s change log to capture all
changes.


### What is included in a user's change log

A user’s change log includes changes to shared drives they're a member of as well
as changes to files in the user's corpus. For more information about corpora, see
Changes and revisions overview
.

These shared drive changes appear on the user’s change log:

- The user becomes a member of a shared drive.
- The user is no longer a member of a shared drive.
- There is a directly relevant change to a shared drive in which the user is a
member, for example:
The user’s access level on that shared drive changed.
The shared drive is renamed.
- The user’s access level on that shared drive changed.
- The shared drive is renamed.
When a user becomes a member of a shared drive, a single change event
for the shared drive appears in the user's change log. This implies
access to all items in the shared drive. The user does not receive changes for
items contained inside the shared drive when they become a member.

Members of a shared drive
may
see change events for items in a shared drive based
on their usage. However, applications should not rely on these events when the
user is a member of the shared drive. Instead, use the shared drive's change log to
track changes.

If a non-member is granted file access to individual items in a shared drive,
changes to those items are tracked in the user's change log. This is the same
as non-shared Drive items that are shared directly with users.


### Changes that appear on a shared drive change log

If a user is a member of a shared drive, they can access that shared drive's change
log which contains:

- Any changes to the shared drive itself, such as addition or removal of a member
- Direct changes to the items contained in the shared drive.

### Syncing permissions and capabilities

Permission changes to shared drive or items inside a shared drive are only
reflected on the item itself. While all direct or indirect children of that
item will inherit this change there will not be a separate entry in the change
log for each of those items. Clients must either
propagate the new capabilities or refetch each item if a parent has
changed in order to fully reconstruct the changes.

Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2026-04-23 UTC.


---

# Files and folders overview Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/guides/about-files

- Home
- Google Workspace
- Google Drive
- Guides
Google Drive organizes files in collections, describes files by types, and
provides specific attributes for each file to facilitate file manipulation.

The Google Drive API represents files stored on Drive as a
files
resource.


## Ownership

Drive organizes files based on the user's relationship with the
content and its storage location.
Collections
are specified as part of the
file's metadata to show which group of files the file is stored with inside
Drive. The main difference between My Drive and
shared drive collections is file ownership. A single user is the owner of files
in their My Drive, whereas a group or organization owns files in
a shared drive.


## File types

Drive describes files by types. This list shows all available
file types:

A container you can use to organize other types of files on
Drive. Folders are files that only contain metadata, and have
the MIME type
application/vnd.google-apps.folder
. For more information,
see
Create and populate folders
.

Note:
A single file stored on My Drive can be in multiple
folders. A single file stored on a
shared
drive
can only have one parent folder.

A file that a Google Workspace application
creates, such as Google Docs, Sheets, or
Slides. The MIME type format is
application/vnd.google-apps.*app*
where
app
is the application name
(such as
application/vnd.google-apps.spreadsheet
for a
Sheets file). For a list of Drive and
Google Workspace-specific MIME types, see
Google Workspace and
Google Drive supported MIME types
.

A metadata-only file that points to another file on Drive. The
shortcut file MIME type is
application/vnd.google-apps.shortcut
. For more
information, see
Create a shortcut to a Drive
file
.

A metadata-only file that links to content stored on a third-party storage
system. The third-party shortcut file MIME type is
application/vnd.google-apps.drive-sdk
. For more information, see
Create a
shortcut file to content stored by your
app
.


## File characteristics

This list shows some characteristics of a Drive file:


## File organization

The Drive API organizes files into storage locations, called
spaces
,
and collections, called
corpora
.

Specific storage locations that are isolated from each other. All content in
Drive is stored in one of these two defined spaces:
drive
and
appDataFolder
.

- drive
: Includes all user-visible files created in
Drive. PDFs, documents, Google Docs, shortcuts, and
other content the user uploads is located in the
drive
space.
drive
: Includes all user-visible files created in
Drive. PDFs, documents, Google Docs, shortcuts, and
other content the user uploads is located in the
drive
space.

- appDataFolder
: Includes per-user application data. Applications
typically store configuration files and other data not intended to be
directly accessible by users.
appDataFolder
: Includes per-user application data. Applications
typically store configuration files and other data not intended to be
directly accessible by users.

Files cannot move between
spaces
.

Collections of files used to narrow the scope of file and folder searches. The
corpora for Drive are:
user
,
domain
,
drive
, and
allDrives
.

- user
: Includes all files created by and opened by the user in "My
Drive", and those shared directly with the user in
"Shared with me."
user
: Includes all files created by and opened by the user in "My
Drive", and those shared directly with the user in
"Shared with me."

- drive
: Includes all files contained in a single shared drive, as
indicated by the
driveId
.
drive
: Includes all files contained in a single shared drive, as
indicated by the
driveId
.

- domain
: Includes all searchable files shared with the user's domain.
domain
: Includes all searchable files shared with the user's domain.

- allDrives
: Includes all files in shared drives where the user is a
member, and all files in "My Drive" and "Shared with me."
Use the
allDrives
corpora with caution as it has a broad scope and can
affect performance. When possible, use
user
or
drive
instead of
allDrives
for efficiency.
allDrives
: Includes all files in shared drives where the user is a
member, and all files in "My Drive" and "Shared with me."
Use the
allDrives
corpora with caution as it has a broad scope and can
affect performance. When possible, use
user
or
drive
instead of
allDrives
for efficiency.

Files can move freely between
corpora
as permissions and ownership change.


## Related topics

Here are a few next steps you might take:

- Learn how to
Create and manage files
.
- Learn how to
Create and populate folders
.
- Learn how to
Upload file data
.
- Learn how to
Download and export files
.
- Learn how to
Store application-specific data
.
- Learn how to
Display the Google Picker
on a page.
Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2026-04-20 UTC.


---

# Labels overview Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/guides/about-labels

- Home
- Google Workspace
- Google Drive
- Guides
Labels
are metadata that you define to help users organize, find, and apply
policy to files in Google Drive. The Drive API allows developers to
apply labels to files and folders, set label field values, read labels and field
values on files, and search for files using metadata terms defined by the custom
label taxonomy.

Drive labels can support business processes by attaching metadata
to files and folders. Common uses for labels are:

- Classify content to follow an information governance strategy
—Create a
label to identify sensitive content or data that requires special handling.
For example, you might create a badged label (a label with color-coded
option values) titled "Sensitivity" with the values of "Top Secret,"
"Confidential," and "Public."
Classify content to follow an information governance strategy
—Create a
label to identify sensitive content or data that requires special handling.
For example, you might create a badged label (a label with color-coded
option values) titled "Sensitivity" with the values of "Top Secret,"
"Confidential," and "Public."

- Apply policy to items in Drive
—Create labels to manage
Drive content throughout its lifecycle and ensure it adheres
to your organization's record keeping practices. For example, use labels to
manage a data loss policy (DLP) whereby users can't download files with a
"Sensitivity" label set to "Top Secret".
Apply policy to items in Drive
—Create labels to manage
Drive content throughout its lifecycle and ensure it adheres
to your organization's record keeping practices. For example, use labels to
manage a data loss policy (DLP) whereby users can't download files with a
"Sensitivity" label set to "Top Secret".

- Curate and find files
—Create labels to increase searchability of your
company's content by letting people in your organization find items based on
labels and their fields. For example, apply a "Signature Status" label set
to "Awaiting Signature" to all contracts awaiting signature by a specific
date. Drive search can then return these contracts when
someone searches "awaiting signature".
Curate and find files
—Create labels to increase searchability of your
company's content by letting people in your organization find items based on
labels and their fields. For example, apply a "Signature Status" label set
to "Awaiting Signature" to all contracts awaiting signature by a specific
date. Drive search can then return these contracts when
someone searches "awaiting signature".

Below is a list of common terms used by Drive labels:

Structured metadata placed on a Drive file.
Drive users can assign labels and set label field values
for files. Labels are composed of:

An individual typed, settable component of a label. A label can have zero or
more fields associated with it. Selection and user fields can be set with
multiple values if the field is configured with
ListOptions
in the
Google Drive Labels API
.

The configured label fields available to users for application to
Drive files. Readable and writable through the
Drive Labels API. Also known as the label schema.

An instance of the label. Anytime a label is created, updated, published, or
deprecated, the label revision increments.


## Related topics

- To learn about using labels in Drive, see
Set a label field
on a file
.
- Learn more about the
Drive Labels API
.
Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2026-04-20 UTC.


---

# Google Drive API overview Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/guides/about-sdk

- Home
- Google Workspace
- Google Drive
- Guides
The Google Drive API lets you create apps that use Google Drive cloud storage.
You can develop applications that integrate with Drive, and
create robust functionality in your application using the Drive API.

This diagram shows the relationship between your Drive app, the
Drive API, and Drive:

These terms define the key components shown in Figure 1:


## What can you do with the Drive API?

You can use the Drive API to:

- Download files
from Drive
and
upload files
to Drive.
- Search for files and folders
stored in
Drive. Create complex search queries that return any of the
file metadata fields in the
files
resource.
- Let users
share files, folders, and drives
to collaborate on content.
- Combine with the
Google Picker API
to search all
files in Drive, then return the filename, URL, last modified
date, and user.
- Create
third-party shortcuts
that
are external links to data stored outside of Drive, in a
different datastore or cloud storage system.
- Create a dedicated Drive folder to
store
application-specific data
so the app cannot access
all the user's content stored in Drive.
- Monitor or respond to file activity using
Google Drive
events
.
- Integrate your Drive-enabled app with the
Drive UI
using the
Google Drive UI
. It's Google's standard web UI that you can
use to create, organize, discover, and share Drive files.
- Apply
labels
to Drive files,
set label field values, read label field values on files, and search for
files using label metadata terms defined by the custom label taxonomy.

|  | Want to see the Google Drive API in action?
The Google Workspace Developers channel offers videos about tips,
 tricks, and the latest features.
Subscribe now |
| --- | --- |


## Related topics

- To learn about developing with Google Workspace APIs, including handling
authentication and authorization, see
Develop on
Google Workspace
.
To learn about developing with Google Workspace APIs, including handling
authentication and authorization, see
Develop on
Google Workspace
.

- To learn how to configure and run a Drive API app, read the
Quickstarts
.
To learn how to configure and run a Drive API app, read the
Quickstarts
.

Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2026-04-20 UTC.


---

# Shared drives overview Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/guides/about-shareddrives

- Home
- Google Workspace
- Google Drive
- Guides
A shared drive is an organizational structure within Google Drive that lives
parallel to
My Drive
.
Shared drives support files owned by an organization rather than an individual
user. An individual file can be organized within a shared drive or My
Drive, but not both. However,
Drive
shortcuts
can be used to point to files or folders
from shared drives to My Drive, or the other way around.


## Access control

Shared drives use a permission model similar to other content in
Drive. Unlike files in My Drive, a group of users
owns content within a shared drive. For more information about permissions, see
Share files, folders, and drives
.


### Permission propagation

Like items in My Drive, permissions on parent items propagate
downward to their children. However, within a shared drive, permissions are
strictly expansive. For example, a user that has
role=commenter
for a shared
drive cannot have their access level reduced at another point within the folder
hierarchy. However, their access can be increased for a certain set of files.

Shared drive files must have exactly one parent. This means that shared drive
files belong to a single shared drive and are located in a single location
within that shared drive. Having a single location simplifies permission rules
for shared drive files.


### Compare member and file access

There are two classes of
permissions
in
shared drives:

- Member permissions
are for users who have been granted access to the
shared drive, either directly or through a group. Members can view the
shared drive metadata, such as the shared drive's name. Members have access
to all files within the shared drive, with the access level depending on the
role
given to the member, such as
commenter
or
reader
.
Member permissions
are for users who have been granted access to the
shared drive, either directly or through a group. Members can view the
shared drive metadata, such as the shared drive's name. Members have access
to all files within the shared drive, with the access level depending on the
role
given to the member, such as
commenter
or
reader
.

- File access permissions
are for users who have been granted access to a
subset of files within the shared drive. For example, sharing a single file
to a user creates a file access permission.
File access permissions
are for users who have been granted access to a
subset of files within the shared drive. For example, sharing a single file
to a user creates a file access permission.

An individual user can be a member of a shared drive
and
have file access
permissions for files contained within the shared drive. A file access
permission might be superseded if the user's membership in the shared drive
grants them a greater level of access.

File permissions are revoked when the user is no longer a member of the shared
drive, or if their member access level is reduced. Users also lose access to any
files and folders in the shared drive that were directly shared with them.


### Roles for shared drives

As with items in My Drive, each user in a shared drive is granted
access with a specific role. These roles are used for shared drives:

- The
fileOrganizer
role allows users to organize files within a shared
drive and to move content into the trash.
The
fileOrganizer
role allows users to organize files within a shared
drive and to move content into the trash.

- The
organizer
role grants the same privileges as the
fileOrganizer
. It
also allows users to permanently remove content and modify shared drive name
and membership.
The
organizer
role grants the same privileges as the
fileOrganizer
. It
also allows users to permanently remove content and modify shared drive name
and membership.

- The
writer
role allows users to add files to shared drives and to share a
shared drive item.
The
writer
role allows users to add files to shared drives and to share a
shared drive item.

The
owner
role isn't allowed in shared drives.

For more information about roles and operations allowed in a shared drive, see
Roles and permissions
.


### Members and organizer rules

Shared drives have both the
organizerCount
and
memberCount
fields. The
values for these fields can decide who can access the shared drive. The
following are the rules for
organizerCount
and
memberCount
fields:

- Only administrators can manage a shared drive with an
organizerCount
of
zero.
Only administrators can manage a shared drive with an
organizerCount
of
zero.

- Only administrators can access a shared drive with a
memberCount
of zero.
Only administrators can access a shared drive with a
memberCount
of zero.

- Only administrators can access a shared drive with an
organizerCount
or
memberCount
greater than zero. This applies only if the remaining
permissions are for empty groups or external users that were added before
turning off sharing outside the domain.
Only administrators can access a shared drive with an
organizerCount
or
memberCount
greater than zero. This applies only if the remaining
permissions are for empty groups or external users that were added before
turning off sharing outside the domain.

- The
organizerCount
and
memberCount
fields don't distinguish between
members of the organization and external members.
The
organizerCount
and
memberCount
fields don't distinguish between
members of the organization and external members.

- Entities written on the file permission can access files inside a shared
drive with a
memberCount
of zero.
Entities written on the file permission can access files inside a shared
drive with a
memberCount
of zero.

For more information, see
Search for shared
drives
.


## Related topics

- Manage folders with limited and expansive access
- Create a shortcut to a Drive file
- How file access works in shared drives
Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2026-04-20 UTC.


---

# Choose Google Drive API scopes Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/guides/api-specific-auth

- Home
- Google Workspace
- Google Drive
- Guides
This document contains Google Drive API-specific authorization and
authentication information. Before reading this document, be sure to read the
Google Workspace's general authentication and authorization information at
Learn about authentication and authorization
.


## Configure OAuth 2.0 for authorization

To authorize your app, the Google Drive API requires you to define OAuth scopes in
two places: the Google Cloud console and your app.

In the Google Cloud console, you must declare the scopes your app needs in its OAuth
consent screen configuration. These are the highest level of permissions your
app can ever request. This serves as a formal request to Google, and the
declared scopes are what Google displays to users on the consent screen. It
allows the user to understand exactly what data and actions your app is
requesting access to.

Configure the OAuth consent screen and choose scopes
to define what information is displayed to users and app reviewers, and register
your app so that you can publish it later.

In your app, when you initiate the API, you must explicitly request the specific
scopes you need for that session. While the Google Cloud console defines the highest
level of permissions your app is allowed to request, the code determines the
actual permissions for a given user. This helps make sure the app only asks for
the permissions needed for a specific task.

You can declare one or more OAuth scopes at a time within your app's code as an
array.

The following code sample shows how to declare multiple OAuth scopes:


### Java


```
List<String>
SCOPES
=
Arrays
.
asList
(
DriveScopes
.
DRIVE_FILE
,
DriveScopes
.
DRIVE_METADATA_READONLY
);
```


### Python


```
SCOPES
=
[
"https://www.googleapis.com/auth/drive.file"
,
"https://www.googleapis.com/auth/drive.metadata.readonly"
,
]
```


### Node.js


```
const
SCOPES
=
[
'https://www.googleapis.com/auth/drive.file'
,
'https://www.googleapis.com/auth/drive.metadata.readonly'
];
```

To see how scopes are declared and used in a full code sample, see
Quickstarts
.


## Drive API scopes

To define the level of access granted to your app, you need to identify and
declare
authorization scopes
. An authorization scope is an OAuth 2.0 URI string
that contains the Google Workspace app name, what kind of data it accesses, and
the level of access. Scopes are your app's requests to work with Google Workspace data, including
 users' Google Account data.
When your app is installed, a user is asked to validate the scopes used
by the app. Generally, you should choose the most narrowly focused scope
possible and avoid requesting scopes that your app doesn't require. Users more
readily grant access to limited, clearly described scopes.
Whenever possible, use non-sensitive scopes as they grant per-file access and
narrow access to specific features needed by an app.
Non-sensitive scopes
The following Drive API scopes are recommended for most use cases:
Scope code
Description
https://www.googleapis.com/auth/drive.appdata
https://www.googleapis.com/auth/drive.appfolder
View and manage the app's own configuration data in your Google Drive.
https://www.googleapis.com/auth/drive.install
Allow apps to appear as an option in the "Open with" or the "New" menu.
https://www.googleapis.com/auth/drive.file
Create new Drive files, or modify existing files, that you open with an app or that the user shares with an app while using the Google Picker API or the app's file picker.
Sensitive scopes
Scope code
Description
https://www.googleapis.com/auth/drive.apps.readonly
View apps authorized to access your Drive.
Restricted scopes
Scope code
Description
https://www.googleapis.com/auth/drive
View and manage all your Drive files.
https://www.googleapis.com/auth/drive.readonly
View and download all your Drive files.
https://www.googleapis.com/auth/drive.activity
View and add to the activity record of files in your Drive.
https://www.googleapis.com/auth/drive.activity.readonly
View the activity record of files in your Drive.
https://www.googleapis.com/auth/drive.meet.readonly
View Drive files created or edited by Google Meet.
https://www.googleapis.com/auth/drive.metadata
View and manage metadata of files in your Drive.
https://www.googleapis.com/auth/drive.metadata.readonly
View metadata for files in your Drive.
https://www.googleapis.com/auth/drive.scripts
Modify your Google Apps Script scripts' behavior.
The scopes in the preceding tables indicate their sensitivity, according to the
following definitions:
Non-sensitive
: These scopes provide the smallest scope of authorization
and only require basic
OAuth App
Verification
. For more
information, see
Verification
requirements
.
Sensitive
: These scopes provide access to specific Google user data that
users authorize for your app. They require additional
OAuth App
Verification
. For more
information, see
Sensitive and Restricted Scope
Requirements
.
Restricted
: These scopes provide wide access to Google user data and
require restricted scope
OAuth App
Verification
. For more
information, see
Google API Services User Data
Policy
and
Additional Requirements
for Specific API
Scopes
.
See also the
Google Drive Terms of
Service
.
If you store restricted scope data on servers (or transmit), then you must
go through a security assessment.
If your app requires access to any other Google APIs, you can add those scopes
as well. For more information about Google API scopes, see
Using OAuth 2.0 to
Access Google APIs
.
For more information about specific OAuth 2.0 scopes, see
OAuth 2.0 Scopes for
Google APIs
.
Qualifications for restricted scopes
Only specific application types are permitted to use restricted scopes for
Google Drive. To qualify, your app must fall into one of the following
categories:
Backup and sync
: Platform-specific and web apps that provide local sync
or automatic backup of users' Drive files.
Productivity and education
: Apps with a primary user interface that
might involve interaction with Drive files, metadata, or
permissions. These apps include task management, note-taking, workgroup
communications, and classroom collaboration apps.
Reporting and security
: Apps that provide user or customer insight into
how files are shared or accessed.
To continue using restricted scopes, you should
prepare your app for restricted
scope
verification
.
Migrate an existing app from restricted scopes
If your Drive app uses restricted scopes, we recommend migrating
to a non-sensitive Drive API scope. Using non-sensitive scopes, such
as
drive.file
, grants per-file and narrow access to specific features needed
by an app.
Many apps can transition to per-file access without any changes.
If you're using your own file picker, we recommend switching to the
Google Picker API
which fully supports
different scopes.
Benefits of the Drive file scope
Using the
drive.file
OAuth scope in combination with the Google Picker API
optimizes both user experience and safety for your app.
The
drive.file
OAuth scope lets users choose which files they want to share
with your app. This gives them more control and confidence that your app's
access to their files is limited and more secure. In contrast, requiring broad
access to all Drive files could discourage users from interacting
with your app.
The following are some reasons why you should use
drive.file
scope:
Usability
: The
drive.file
scope works with all
Drive API
REST Resources
which means you can use it the same way
you use broader OAuth scopes.
Features
: The Google Picker API provides a similar interface to the
Drive UI. This includes several views showing previews and
thumbnails of Drive files, and an inline, modal window so
users never leave the main app.
Convenience
: Apps can apply filters for certain Drive
file types (such as Google Docs, Sheets, and photos) when
using a
filter on Google Picker
files
.
Straightforward verification
: Since
drive.file
is non-sensitive, it
allows for a more streamlined verification process.
Securely store refresh tokens
To access private data using the Drive API, your app must obtain an
access token that grants access to that API. A single access token can grant
varying degrees of access to multiple APIs, governed by the scopes you request.
Because access tokens are short-lived, you must use refresh tokens for long-term
access to the Drive API. A refresh token allows your app to request
new access tokens.
Save refresh tokens in secure, long-term storage and continue to use them as
long as they remain valid.
For more information, see
Using OAuth 2.0 to Access Google
APIs
.
Related topics
For an overview of authentication and authorization in Google Workspace,
see
Learn about authentication &
authorization
.
For an overview of authentication and authorization in Google Cloud, see
Authentication overview
.
To learn more about service accounts, see
Service
accounts
.
For help with troubleshooting, see
Resolve
errors
.

When your app is installed, a user is asked to validate the scopes used
by the app. Generally, you should choose the most narrowly focused scope
possible and avoid requesting scopes that your app doesn't require. Users more
readily grant access to limited, clearly described scopes.
Whenever possible, use non-sensitive scopes as they grant per-file access and
narrow access to specific features needed by an app.
Non-sensitive scopes
The following Drive API scopes are recommended for most use cases:
Scope code
Description
https://www.googleapis.com/auth/drive.appdata
https://www.googleapis.com/auth/drive.appfolder
View and manage the app's own configuration data in your Google Drive.
https://www.googleapis.com/auth/drive.install
Allow apps to appear as an option in the "Open with" or the "New" menu.
https://www.googleapis.com/auth/drive.file
Create new Drive files, or modify existing files, that you open with an app or that the user shares with an app while using the Google Picker API or the app's file picker.
Sensitive scopes
Scope code
Description
https://www.googleapis.com/auth/drive.apps.readonly
View apps authorized to access your Drive.
Restricted scopes
Scope code
Description
https://www.googleapis.com/auth/drive
View and manage all your Drive files.
https://www.googleapis.com/auth/drive.readonly
View and download all your Drive files.
https://www.googleapis.com/auth/drive.activity
View and add to the activity record of files in your Drive.
https://www.googleapis.com/auth/drive.activity.readonly
View the activity record of files in your Drive.
https://www.googleapis.com/auth/drive.meet.readonly
View Drive files created or edited by Google Meet.
https://www.googleapis.com/auth/drive.metadata
View and manage metadata of files in your Drive.
https://www.googleapis.com/auth/drive.metadata.readonly
View metadata for files in your Drive.
https://www.googleapis.com/auth/drive.scripts
Modify your Google Apps Script scripts' behavior.
The scopes in the preceding tables indicate their sensitivity, according to the
following definitions:
Non-sensitive
: These scopes provide the smallest scope of authorization
and only require basic
OAuth App
Verification
. For more
information, see
Verification
requirements
.
Sensitive
: These scopes provide access to specific Google user data that
users authorize for your app. They require additional
OAuth App
Verification
. For more
information, see
Sensitive and Restricted Scope
Requirements
.
Restricted
: These scopes provide wide access to Google user data and
require restricted scope
OAuth App
Verification
. For more
information, see
Google API Services User Data
Policy
and
Additional Requirements
for Specific API
Scopes
.
See also the
Google Drive Terms of
Service
.
If you store restricted scope data on servers (or transmit), then you must
go through a security assessment.
If your app requires access to any other Google APIs, you can add those scopes
as well. For more information about Google API scopes, see
Using OAuth 2.0 to
Access Google APIs
.
For more information about specific OAuth 2.0 scopes, see
OAuth 2.0 Scopes for
Google APIs
.
Qualifications for restricted scopes
Only specific application types are permitted to use restricted scopes for
Google Drive. To qualify, your app must fall into one of the following
categories:
Backup and sync
: Platform-specific and web apps that provide local sync
or automatic backup of users' Drive files.
Productivity and education
: Apps with a primary user interface that
might involve interaction with Drive files, metadata, or
permissions. These apps include task management, note-taking, workgroup
communications, and classroom collaboration apps.
Reporting and security
: Apps that provide user or customer insight into
how files are shared or accessed.
To continue using restricted scopes, you should
prepare your app for restricted
scope
verification
.
Migrate an existing app from restricted scopes
If your Drive app uses restricted scopes, we recommend migrating
to a non-sensitive Drive API scope. Using non-sensitive scopes, such
as
drive.file
, grants per-file and narrow access to specific features needed
by an app.
Many apps can transition to per-file access without any changes.
If you're using your own file picker, we recommend switching to the
Google Picker API
which fully supports
different scopes.
Benefits of the Drive file scope
Using the
drive.file
OAuth scope in combination with the Google Picker API
optimizes both user experience and safety for your app.
The
drive.file
OAuth scope lets users choose which files they want to share
with your app. This gives them more control and confidence that your app's
access to their files is limited and more secure. In contrast, requiring broad
access to all Drive files could discourage users from interacting
with your app.
The following are some reasons why you should use
drive.file
scope:
Usability
: The
drive.file
scope works with all
Drive API
REST Resources
which means you can use it the same way
you use broader OAuth scopes.
Features
: The Google Picker API provides a similar interface to the
Drive UI. This includes several views showing previews and
thumbnails of Drive files, and an inline, modal window so
users never leave the main app.
Convenience
: Apps can apply filters for certain Drive
file types (such as Google Docs, Sheets, and photos) when
using a
filter on Google Picker
files
.
Straightforward verification
: Since
drive.file
is non-sensitive, it
allows for a more streamlined verification process.
Securely store refresh tokens
To access private data using the Drive API, your app must obtain an
access token that grants access to that API. A single access token can grant
varying degrees of access to multiple APIs, governed by the scopes you request.
Because access tokens are short-lived, you must use refresh tokens for long-term
access to the Drive API. A refresh token allows your app to request
new access tokens.
Save refresh tokens in secure, long-term storage and continue to use them as
long as they remain valid.
For more information, see
Using OAuth 2.0 to Access Google
APIs
.
Related topics
For an overview of authentication and authorization in Google Workspace,
see
Learn about authentication &
authorization
.
For an overview of authentication and authorization in Google Cloud, see
Authentication overview
.
To learn more about service accounts, see
Service
accounts
.
For help with troubleshooting, see
Resolve
errors
.

When your app is installed, a user is asked to validate the scopes used
by the app. Generally, you should choose the most narrowly focused scope
possible and avoid requesting scopes that your app doesn't require. Users more
readily grant access to limited, clearly described scopes.

Whenever possible, use non-sensitive scopes as they grant per-file access and
narrow access to specific features needed by an app.


### Non-sensitive scopes

The following Drive API scopes are recommended for most use cases:


| Scope code | Description |
| --- | --- |
| https://www.googleapis.com/auth/drive.appdata
https://www.googleapis.com/auth/drive.appfolder | View and manage the app's own configuration data in your Google Drive. |
| https://www.googleapis.com/auth/drive.install | Allow apps to appear as an option in the "Open with" or the "New" menu. |
| https://www.googleapis.com/auth/drive.file | Create new Drive files, or modify existing files, that you open with an app or that the user shares with an app while using the Google Picker API or the app's file picker. |


### Sensitive scopes


| Scope code | Description |
| --- | --- |
| https://www.googleapis.com/auth/drive.apps.readonly | View apps authorized to access your Drive. |


### Restricted scopes


| Scope code | Description |
| --- | --- |
| https://www.googleapis.com/auth/drive | View and manage all your Drive files. |
| https://www.googleapis.com/auth/drive.readonly | View and download all your Drive files. |
| https://www.googleapis.com/auth/drive.activity | View and add to the activity record of files in your Drive. |
| https://www.googleapis.com/auth/drive.activity.readonly | View the activity record of files in your Drive. |
| https://www.googleapis.com/auth/drive.meet.readonly | View Drive files created or edited by Google Meet. |
| https://www.googleapis.com/auth/drive.metadata | View and manage metadata of files in your Drive. |
| https://www.googleapis.com/auth/drive.metadata.readonly | View metadata for files in your Drive. |
| https://www.googleapis.com/auth/drive.scripts | Modify your Google Apps Script scripts' behavior. |

The scopes in the preceding tables indicate their sensitivity, according to the
following definitions:

- Non-sensitive
: These scopes provide the smallest scope of authorization
and only require basic
OAuth App
Verification
. For more
information, see
Verification
requirements
.
Non-sensitive
: These scopes provide the smallest scope of authorization
and only require basic
OAuth App
Verification
. For more
information, see
Verification
requirements
.

- Sensitive
: These scopes provide access to specific Google user data that
users authorize for your app. They require additional
OAuth App
Verification
. For more
information, see
Sensitive and Restricted Scope
Requirements
.
Sensitive
: These scopes provide access to specific Google user data that
users authorize for your app. They require additional
OAuth App
Verification
. For more
information, see
Sensitive and Restricted Scope
Requirements
.

- Restricted
: These scopes provide wide access to Google user data and
require restricted scope
OAuth App
Verification
. For more
information, see
Google API Services User Data
Policy
and
Additional Requirements
for Specific API
Scopes
.
See also the
Google Drive Terms of
Service
.
If you store restricted scope data on servers (or transmit), then you must
go through a security assessment.
Restricted
: These scopes provide wide access to Google user data and
require restricted scope
OAuth App
Verification
. For more
information, see
Google API Services User Data
Policy
and
Additional Requirements
for Specific API
Scopes
.
See also the
Google Drive Terms of
Service
.

If you store restricted scope data on servers (or transmit), then you must
go through a security assessment.

If your app requires access to any other Google APIs, you can add those scopes
as well. For more information about Google API scopes, see
Using OAuth 2.0 to
Access Google APIs
.

For more information about specific OAuth 2.0 scopes, see
OAuth 2.0 Scopes for
Google APIs
.


## Qualifications for restricted scopes

Only specific application types are permitted to use restricted scopes for
Google Drive. To qualify, your app must fall into one of the following
categories:

- Backup and sync
: Platform-specific and web apps that provide local sync
or automatic backup of users' Drive files.
Backup and sync
: Platform-specific and web apps that provide local sync
or automatic backup of users' Drive files.

- Productivity and education
: Apps with a primary user interface that
might involve interaction with Drive files, metadata, or
permissions. These apps include task management, note-taking, workgroup
communications, and classroom collaboration apps.
Productivity and education
: Apps with a primary user interface that
might involve interaction with Drive files, metadata, or
permissions. These apps include task management, note-taking, workgroup
communications, and classroom collaboration apps.

- Reporting and security
: Apps that provide user or customer insight into
how files are shared or accessed.
Reporting and security
: Apps that provide user or customer insight into
how files are shared or accessed.

To continue using restricted scopes, you should
prepare your app for restricted
scope
verification
.


## Migrate an existing app from restricted scopes

If your Drive app uses restricted scopes, we recommend migrating
to a non-sensitive Drive API scope. Using non-sensitive scopes, such
as
drive.file
, grants per-file and narrow access to specific features needed
by an app.

Many apps can transition to per-file access without any changes.

If you're using your own file picker, we recommend switching to the
Google Picker API
which fully supports
different scopes.


### Benefits of the Drive file scope

Using the
drive.file
OAuth scope in combination with the Google Picker API
optimizes both user experience and safety for your app.

The
drive.file
OAuth scope lets users choose which files they want to share
with your app. This gives them more control and confidence that your app's
access to their files is limited and more secure. In contrast, requiring broad
access to all Drive files could discourage users from interacting
with your app.

The following are some reasons why you should use
drive.file
scope:

- Usability
: The
drive.file
scope works with all
Drive API
REST Resources
which means you can use it the same way
you use broader OAuth scopes.
Usability
: The
drive.file
scope works with all
Drive API
REST Resources
which means you can use it the same way
you use broader OAuth scopes.

- Features
: The Google Picker API provides a similar interface to the
Drive UI. This includes several views showing previews and
thumbnails of Drive files, and an inline, modal window so
users never leave the main app.
Features
: The Google Picker API provides a similar interface to the
Drive UI. This includes several views showing previews and
thumbnails of Drive files, and an inline, modal window so
users never leave the main app.

- Convenience
: Apps can apply filters for certain Drive
file types (such as Google Docs, Sheets, and photos) when
using a
filter on Google Picker
files
.
Convenience
: Apps can apply filters for certain Drive
file types (such as Google Docs, Sheets, and photos) when
using a
filter on Google Picker
files
.

- Straightforward verification
: Since
drive.file
is non-sensitive, it
allows for a more streamlined verification process.
Straightforward verification
: Since
drive.file
is non-sensitive, it
allows for a more streamlined verification process.


## Securely store refresh tokens

To access private data using the Drive API, your app must obtain an
access token that grants access to that API. A single access token can grant
varying degrees of access to multiple APIs, governed by the scopes you request.

Because access tokens are short-lived, you must use refresh tokens for long-term
access to the Drive API. A refresh token allows your app to request
new access tokens.

Save refresh tokens in secure, long-term storage and continue to use them as
long as they remain valid.

For more information, see
Using OAuth 2.0 to Access Google
APIs
.


## Related topics

- For an overview of authentication and authorization in Google Workspace,
see
Learn about authentication &
authorization
.
- For an overview of authentication and authorization in Google Cloud, see
Authentication overview
.
- To learn more about service accounts, see
Service
accounts
.
- For help with troubleshooting, see
Resolve
errors
.
Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2026-04-20 UTC.


---

# Store application-specific data Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/guides/appdata

- Home
- Google Workspace
- Google Drive
- Guides
The
application data folder
is a special hidden folder that your app can use
to store application-specific data, such as configuration files. The application
data folder is automatically created when you attempt to create a file in it.
Use this folder to store any files that the user shouldn't directly interact
with. This folder is only accessible by your app and its contents are hidden
from the user and from other Google Drive apps.

The application data folder is deleted when a user uninstalls your app from
their My Drive. Users can also delete your app's data folder manually.


## Application data folder scope

Before you can access the application data folder, you must request access to
the
https://www.googleapis.com/auth/drive.appdata
non-sensitive scope. For
more information about scopes and how to request access to them, refer to
Choose Google Drive API scopes
. For more
information about specific OAuth 2.0 scopes, see
OAuth 2.0 Scopes for Google
APIs
.


## How the application data folder differs from Drive backup folders

The application data folder is separate from your Drive backup
folder.

The application data folder is a configuration folder that's created per
third-party app and each third-party app can store data in it. Only the
application that created the data in the
appDataFolder
can access it. The
folder can't be accessed using the Drive user interface (UI).

Your
Drive backup
folder
is a reserved folder that
Drive writes device backups to and it's visible in the
Drive UI.


## Constraints on the application data folder

The following constraints are enforced when working with the application data
folder:

- You can't share files or folders inside the application data folder.
Attempting to do so generates a
notSupportedForAppDataFolderFiles
error
with the following error message: "Method not supported for files within the
Application Data folder."
You can't share files or folders inside the application data folder.
Attempting to do so generates a
notSupportedForAppDataFolderFiles
error
with the following error message: "Method not supported for files within the
Application Data folder."

- You can't move files in the
appDataFolder
between storage locations
(spaces). Attempting to do so generates a
notSupportedForAppDataFolderFiles
error with the following error message:
"Method not supported for files within the Application Data folder." For
more information, see
File
organization
.
You can't move files in the
appDataFolder
between storage locations
(spaces). Attempting to do so generates a
notSupportedForAppDataFolderFiles
error with the following error message:
"Method not supported for files within the Application Data folder." For
more information, see
File
organization
.

- You can't trash files or folders inside the application data folder.
Attempting to do so generates a
notSupportedForAppDataFolderFiles
error
with the following error message: "Files within the Application Data folder
cannot be trashed."
You can't trash files or folders inside the application data folder.
Attempting to do so generates a
notSupportedForAppDataFolderFiles
error
with the following error message: "Files within the Application Data folder
cannot be trashed."


## Create a file in the application data folder

To create a file in the application data folder, specify
appDataFolder
in the
parents
property of the file and use the
files.create
method to create the file in
the folder.

The following code sample shows how to insert a file into a folder using a
client library and a curl command.


### Java


```
import
com.google.api.client.googleapis.json.GoogleJsonResponseException
;
import
com.google.api.client.http.FileContent
;
import
com.google.api.client.http.HttpRequestInitializer
;
import
com.google.api.client.http.javanet.NetHttpTransport
;
import
com.google.api.client.json.gson.GsonFactory
;
import
com.google.api.services.drive.Drive
;
import
com.google.api.services.drive.DriveScopes
;
import
com.google.api.services.drive.model.File
;
import
com.google.auth.http.HttpCredentialsAdapter
;
import
com.google.auth.oauth2.GoogleCredentials
;
import
java.io.IOException
;
import
java.util.Arrays
;
import
java.util.Collections
;
/**
* Class to demonstrate use-case of create file in the application data folder.
*/
public
class
UploadAppData
{
/**
* Creates a file in the application data folder.
*
* @return Created file's Id.
*/
public
static
String
uploadAppData
()
throws
IOException
{
/*Load pre-authorized user credentials from the environment.
TODO(developer) - See https://developers.google.com/identity for
guides on implementing OAuth2 for your application.*/
GoogleCredentials
credentials
=
null
;
try
{
credentials
=
GoogleCredentials
.
getApplicationDefault
()
.
createScoped
(
Arrays
.
asList
(
DriveScopes
.
DRIVE_APPDATA
));
}
catch
(
IOException
e
)
{
e
.
printStackTrace
();
}
HttpRequestInitializer
requestInitializer
=
new
HttpCredentialsAdapter
(
credentials
);
// Build a new authorized API client service.
Drive
service
=
new
Drive
.
Builder
(
new
NetHttpTransport
(),
GsonFactory
.
getDefaultInstance
(),
requestInitializer
)
.
setApplicationName
(
"Drive samples"
)
.
build
();
try
{
// File's metadata.
File
fileMetadata
=
new
File
();
fileMetadata
.
setName
(
"config.json"
);
fileMetadata
.
setParents
(
Collections
.
singletonList
(
"appDataFolder"
));
java
.
io
.
File
filePath
=
new
java
.
io
.
File
(
"files/config.json"
);
FileContent
mediaContent
=
new
FileContent
(
"application/json"
,
filePath
);
File
file
=
service
.
files
().
create
(
fileMetadata
,
mediaContent
)
.
setFields
(
"id"
)
.
execute
();
System
.
out
.
println
(
"File ID: "
+
file
.
getId
());
return
file
.
getId
();
}
catch
(
GoogleJsonResponseException
e
)
{
// TODO(developer) - handle error appropriately
System
.
err
.
println
(
"Unable to create file: "
+
e
.
getDetails
());
throw
e
;
}
}
}
```


### Python


```
import
google.auth
from
googleapiclient.discovery
import
build
from
googleapiclient.errors
import
HttpError
from
googleapiclient.http
import
MediaFileUpload
def
upload_appdata
():
"""Insert a file in the application data folder and prints file Id.
Returns : ID's of the inserted files
Load pre-authorized user credentials from the environment.
TODO(developer) - See https://developers.google.com/identity
for guides on implementing OAuth2 for the application.
"""
creds
,
_
=
google
.
auth
.
default
()
try
:
# call drive api client
service
=
build
(
"drive"
,
"v3"
,
credentials
=
creds
)
# pylint: disable=maybe-no-member
file_metadata
=
{
"name"
:
"abc.txt"
,
"parents"
:
[
"appDataFolder"
]}
media
=
MediaFileUpload
(
"abc.txt"
,
mimetype
=
"text/txt"
,
resumable
=
True
)
file
=
(
service
.
files
()
.
create
(
body
=
file_metadata
,
media_body
=
media
,
fields
=
"id"
)
.
execute
()
)
print
(
f
'File ID:
{
file
.
get
(
"id"
)
}
'
)
except
HttpError
as
error
:
print
(
f
"An error occurred:
{
error
}
"
)
file
=
None
return
file
.
get
(
"id"
)
if
__name__
==
"__main__"
:
upload_appdata
()
```


### Node.js


```
import
fs
from
'node:fs'
;
import
{
GoogleAuth
}
from
'google-auth-library'
;
import
{
google
}
from
'googleapis'
;
/**
* Uploads a file to the application data folder.
* @return {Promise<string>} The ID of the uploaded file.
*/
async
function
uploadAppdata
()
{
// Authenticate with Google and get an authorized client.
// TODO (developer): Use an appropriate auth mechanism for your app.
const
auth
=
new
GoogleAuth
({
scopes
:
'https://www.googleapis.com/auth/drive.appdata'
,
});
// Create a new Drive API client (v3).
const
service
=
google
.
drive
({
version
:
'v3'
,
auth
});
// The metadata for the file to be uploaded.
const
fileMetadata
=
{
name
:
'config.json'
,
parents
:
[
'appDataFolder'
],
};
// The media content to be uploaded.
const
media
=
{
mimeType
:
'application/json'
,
body
:
fs
.
createReadStream
(
'files/config.json'
),
};
// Upload the file to the application data folder.
const
file
=
await
service
.
files
.
create
({
requestBody
:
fileMetadata
,
media
,
fields
:
'id'
,
});
// Print the ID of the uploaded file.
console
.
log
(
'File Id:'
,
file
.
data
.
id
);
if
(
!
file
.
data
.
id
)
{
throw
new
Error
(
'File ID not found.'
);
}
return
file
.
data
.
id
;
}
```


### PHP


```
<
?php
use Google\Client;
use Google\Service\Drive;
function uploadAppData()
{
try {
$client = new Client();
$client->useApplicationDefaultCredentials();
$client->addScope(Drive::DRIVE);
$client->addScope(Drive::DRIVE_APPDATA);
$driveService = new Drive($client);
$fileMetadata = new Drive\DriveFile(array(
'name' => 'config.json',
'parents' => array('appDataFolder')
));
$content = file_get_contents('../files/config.json');
$file = $driveService->files->create($fileMetadata, array(
'data' => $content,
'mimeType' => 'application/json',
'uploadType' => 'multipart',
'fields' => 'id'));
printf("File ID: %s\n", $file->id);
return $file->id;
} catch(Exception $e) {
echo "Error Message: ".$e;
}
}
```


### .NET


```
using
Google.Apis.Auth.OAuth2
;
using
Google.Apis.Drive.v3
;
using
Google.Apis.Services
;
namespace
DriveV3Snippets
{
// Class of demonstrate the use of Drive upload app data.
public
class
UploadAppData
{
/// <summary>
/// Insert a file in the application data folder and prints file Id.
/// </summary>
/// <param name="filePath">File path to upload.</param>
/// <returns>ID's of the inserted files, null otherwise.</returns>
public
static
string
DriveUploadAppData
(
string
filePath
)
{
try
{
/* Load pre-authorized user credentials from the environment.
TODO(developer) - See https://developers.google.com/identity for
guides on implementing OAuth2 for your application. */
GoogleCredential
credential
=
GoogleCredential
.
GetApplicationDefault
()
.
CreateScoped
(
DriveService
.
Scope
.
DriveAppdata
);
// Create Drive API service.
var
service
=
new
DriveService
(
new
BaseClientService
.
Initializer
{
HttpClientInitializer
=
credential
,
ApplicationName
=
"Drive API Snippets"
});
var
fileMetadata
=
new
Google
.
Apis
.
Drive
.
v3
.
Data
.
File
()
{
Name
=
"config.json"
,
Parents
=
new
List<string>
()
{
"appDataFolder"
}
};
FilesResource
.
CreateMediaUpload
request
;
using
(
var
stream
=
new
FileStream
(
filePath
,
FileMode
.
Open
))
{
request
=
service
.
Files
.
Create
(
fileMetadata
,
stream
,
"application/json"
);
request
.
Fields
=
"id"
;
request
.
Upload
();
}
var
file
=
request
.
ResponseBody
;
// Prints the file id.
Console
.
WriteLine
(
"File ID: "
+
file
.
Id
);
return
file
.
Id
;
}
catch
(
Exception
e
)
{
// TODO(developer) - handle error appropriately
if
(
e
is
AggregateException
)
{
Console
.
WriteLine
(
"Credential Not found"
);
}
else
{
throw
;
}
}
return
null
;
}
}
}
```


### curl

Request
:


```bash
curl
--request
POST
\
'https://content.googleapis.com/drive/v3/files'
\
-H
'authorization: Bearer
ACCESS_TOKEN
'
\
-H
'content-type: application/json'
\
-H
'x-origin: https://explorer.apis.google.com'
\
--data-raw
'{"name": "config.json", "parents":["appDataFolder"]}'
```

Replace
ACCESS_TOKEN
with your app's
OAuth
2.0
token.

Response
:


```
{
"kind"
:
"drive#file"
,
"id"
:
FILE_ID
,
"name"
:
"config.json"
,
"mimeType"
:
"application/json"
}
```

For further information on creating files in folders, refer to
Create and
populate folders
.


## Search for files in the application data folder

To search for files in the application data folder, set the
spaces
field to
appDataFolder
and use the
files.list
method.

The following code sample shows how to search for files in the application data
folder using a client library and a curl command.


```
import
com.google.api.client.googleapis.json.GoogleJsonResponseException
;
import
com.google.api.client.http.HttpRequestInitializer
;
import
com.google.api.client.http.javanet.NetHttpTransport
;
import
com.google.api.client.json.gson.GsonFactory
;
import
com.google.api.services.drive.Drive
;
import
com.google.api.services.drive.DriveScopes
;
import
com.google.api.services.drive.model.File
;
import
com.google.api.services.drive.model.FileList
;
import
com.google.auth.http.HttpCredentialsAdapter
;
import
com.google.auth.oauth2.GoogleCredentials
;
import
java.io.IOException
;
import
java.util.Arrays
;
/**
* Class to demonstrate use-case of list 10 files in the application data folder.
*/
public
class
ListAppData
{
/**
* list down files in the application data folder.
*
* @return list of 10 files.
*/
public
static
FileList
listAppData
()
throws
IOException
{
/*Load pre-authorized user credentials from the environment.
TODO(developer) - See https://developers.google.com/identity for
guides on implementing OAuth2 for your application.*/
GoogleCredentials
credentials
=
null
;
try
{
credentials
=
GoogleCredentials
.
getApplicationDefault
()
.
createScoped
(
Arrays
.
asList
(
DriveScopes
.
DRIVE_APPDATA
));
}
catch
(
IOException
e
)
{
e
.
printStackTrace
();
}
HttpRequestInitializer
requestInitializer
=
new
HttpCredentialsAdapter
(
credentials
);
// Build a new authorized API client service.
Drive
service
=
new
Drive
.
Builder
(
new
NetHttpTransport
(),
GsonFactory
.
getDefaultInstance
(),
requestInitializer
)
.
setApplicationName
(
"Drive samples"
)
.
build
();
try
{
FileList
files
=
service
.
files
().
list
()
.
setSpaces
(
"appDataFolder"
)
.
setFields
(
"nextPageToken, files(id, name)"
)
.
setPageSize
(
10
)
.
execute
();
for
(
File
file
:
files
.
getFiles
())
{
System
.
out
.
printf
(
"Found file: %s (%s)\n"
,
file
.
getName
(),
file
.
getId
());
}
return
files
;
}
catch
(
GoogleJsonResponseException
e
)
{
// TODO(developer) - handle error appropriately
System
.
err
.
println
(
"Unable to list files: "
+
e
.
getDetails
());
throw
e
;
}
}
}
```


```
import
google.auth
from
googleapiclient.discovery
import
build
from
googleapiclient.errors
import
HttpError
def
list_appdata
():
"""List all files inserted in the application data folder
prints file titles with Ids.
Returns : List of items
Load pre-authorized user credentials from the environment.
TODO(developer) - See https://developers.google.com/identity
for guides on implementing OAuth2 for the application.
"""
creds
,
_
=
google
.
auth
.
default
()
try
:
# call drive api client
service
=
build
(
"drive"
,
"v3"
,
credentials
=
creds
)
# pylint: disable=maybe-no-member
response
=
(
service
.
files
()
.
list
(
spaces
=
"appDataFolder"
,
fields
=
"nextPageToken, files(id, name)"
,
pageSize
=
10
,
)
.
execute
()
)
for
file
in
response
.
get
(
"files"
,
[]):
# Process change
print
(
f
'Found file:
{
file
.
get
(
"name"
)
}
,
{
file
.
get
(
"id"
)
}
'
)
except
HttpError
as
error
:
print
(
f
"An error occurred:
{
error
}
"
)
response
=
None
return
response
.
get
(
"files"
)
if
__name__
==
"__main__"
:
list_appdata
()
```


```
/**
* Copyright 2022 Google LLC
*
* Licensed under the Apache License, Version 2.0 (the "License");
* you may not use this file except in compliance with the License.
* You may obtain a copy of the License at
*
*     https://www.apache.org/licenses/LICENSE-2.0
*
* Unless required by applicable law or agreed to in writing, software
* distributed under the License is distributed on an "AS IS" BASIS,
* WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
* See the License for the specific language governing permissions and
* limitations under the License.
*/
import
{
GoogleAuth
}
from
'google-auth-library'
;
import
{
google
}
from
'googleapis'
;
/**
* Lists all files in the application data folder.
* @return {Promise<object[]>} A list of files.
*/
async
function
listAppdata
()
{
// Authenticate with Google and get an authorized client.
// TODO (developer): Use an appropriate auth mechanism for your app.
const
auth
=
new
GoogleAuth
({
scopes
:
'https://www.googleapis.com/auth/drive.appdata'
,
});
// Create a new Drive API client (v3).
const
service
=
google
.
drive
({
version
:
'v3'
,
auth
});
// List the files in the application data folder.
const
result
=
await
service
.
files
.
list
({
spaces
:
'appDataFolder'
,
fields
:
'nextPageToken, files(id, name)'
,
pageSize
:
100
,
});
// Print the name and ID of each file.
(
result
.
data
.
files
??
[]).
forEach
((
file
)
=
>
{
console
.
log
(
'Found file:'
,
file
.
name
,
file
.
id
);
});
return
result
.
data
.
files
??
[];
}
export
{
listAppdata
};
```


```
<
?php
use Google\Client;
use Google\Service\Drive;
function listAppData()
{
try {
$client = new Client();
$client->useApplicationDefaultCredentials();
$client->addScope(Drive::DRIVE);
$driveService = new Drive($client);
$response = $driveService->files->listFiles(array(
'spaces' => 'appDataFolder',
'fields' => 'nextPageToken, files(id, name)',
'pageSize' => 10
));
foreach ($response->files as $file) {
printf("Found file: %s (%s)", $file->name, $file->id);
}
return $response->files;
}catch(Exception $e) {
echo "Error Message: ".$e;
}
}
```


```
using
Google.Apis.Auth.OAuth2
;
using
Google.Apis.Drive.v3
;
using
Google.Apis.Drive.v3.Data
;
using
Google.Apis.Services
;
namespace
DriveV3Snippets
{
// Class to demonstrate use-case of Drive's list files in the application data folder.
public
class
ListAppData
{
/// <summary>
/// List down files in the application data folder.
/// </summary>
/// <returns>list of 10 files, null otherwise.</returns>
public
static
FileList
DriveListAppData
()
{
try
{
/* Load pre-authorized user credentials from the environment.
TODO(developer) - See https://developers.google.com/identity for
guides on implementing OAuth2 for your application. */
GoogleCredential
credential
=
GoogleCredential
.
GetApplicationDefault
()
.
CreateScoped
(
DriveService
.
Scope
.
DriveAppdata
);
// Create Drive API service.
var
service
=
new
DriveService
(
new
BaseClientService
.
Initializer
{
HttpClientInitializer
=
credential
,
ApplicationName
=
"Drive API Snippets"
});
var
request
=
service
.
Files
.
List
();
request
.
Spaces
=
"appDataFolder"
;
request
.
Fields
=
"nextPageToken, files(id, name)"
;
request
.
PageSize
=
10
;
var
result
=
request
.
Execute
();
foreach
(
var
file
in
result
.
Files
)
{
// Prints the list of 10 file names.
Console
.
WriteLine
(
"Found file: {0} ({1})"
,
file
.
Name
,
file
.
Id
);
}
return
result
;
}
catch
(
Exception
e
)
{
// TODO(developer) - handle error appropriately
if
(
e
is
AggregateException
)
{
Console
.
WriteLine
(
"Credential Not found"
);
}
else
{
throw
;
}
}
return
null
;
}
}
}
```


```bash
curl
\
-X
GET
\
-H
"Authorization: Bearer
ACCESS_TOKEN
"
\
"https://www.googleapis.com/drive/v3/files?spaces=appDataFolder&fields=files(id,name,mimeType,size,modifiedTime)"
```


```
{
"files"
:
[
{
"mimeType"
:
"application/json"
,
"size"
:
"256"
,
"id"
:
FILE_ID
,
"name"
:
"config.json"
,
"modifiedTime"
:
"2025-04-03T23:40:05.860Z"
},
{
"mimeType"
:
"text/plain"
,
"size"
:
"128"
,
"id"
:
FILE_ID
,
"name"
:
"user_settings.txt"
,
"modifiedTime"
:
"2025-04-02T17:52:29.020Z"
}
]
}
```


## Download files from the application data folder

To download a file from the application data folder, use the
files.get
method with the
alt=media
URL parameter to
retrieve the file contents in the response body. For more information, and to
view code samples, go to
Download blob file
content
.

The following code sample shows how to download files in the application data
folder using a curl command. The response body will vary depending on what's
saved.


```bash
curl
\
-X
GET
\
-H
"Authorization: Bearer
ACCESS_TOKEN
"
\
"https://www.googleapis.com/drive/v3/files/
FILE_ID
?alt=media"
```

Replace the following:

- ACCESS_TOKEN
: Your app's
OAuth
2.0
token.
- FILE_ID
: The ID of the file you want to download.
Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2026-04-20 UTC.


---

# Manage approvals Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/guides/approvals

- Home
- Google Workspace
- Google Drive
- Guides
This document explains how to manage approvals in the Google Drive API.

Users can send documents in Google Drive through a formal approval process.
You can use this process to get approval on a contract review or an official
document before publication. An approval tracks the status of both the review
(such as In Progress, Approved, or Declined) and the reviewers involved.
Approvals are an excellent way to validate content and to keep a record of
reviewers.

You can create and manage content approvals in Drive. The
Google Drive API provides the
approvals
resource
to work with file approvals. The methods of the
approvals
resource work on
items within Drive, Google Docs, and other Google Workspace
editors. Reviewers can approve, reject, or leave feedback on the documents
directly.


## Before you begin

- Your file should contain the
canStartApproval
capability . To check file capabilities, call the
get
method on the
files
resource with the
fileId
path parameter and use the
canStartApproval
capability field in
the
fields
parameter. For more information, see
Understand file
capabilities
.
The boolean
canStartApproval
capability is
false
when:
Administrator settings restrict access to the feature.
Your Google Workspace edition is ineligible.
The file is owned by a user outside your domain.
The user lacks the
role=writer
permission on the file.
Your file should contain the
canStartApproval
capability . To check file capabilities, call the
get
method on the
files
resource with the
fileId
path parameter and use the
canStartApproval
capability field in
the
fields
parameter. For more information, see
Understand file
capabilities
.

The boolean
canStartApproval
capability is
false
when:

- Administrator settings restrict access to the feature.
- Your Google Workspace edition is ineligible.
- The file is owned by a user outside your domain.
- The user lacks the
role=writer
permission on the file.
- Make sure you manually share the target file with the reviewers.
Drive doesn't do this automatically. If a reviewer doesn't
have file access, the approval request will succeed, but they won't receive
notifications or be able to view the file.
Make sure you manually share the target file with the reviewers.
Drive doesn't do this automatically. If a reviewer doesn't
have file access, the approval request will succeed, but they won't receive
notifications or be able to view the file.


## Concepts

The following key concepts form the foundation of approvals.


### Approval status

When you request a document approval, the approval process ensures every
reviewer approves the same version of the content. If the file is edited after a
reviewer approves the request, and before the request is complete, the
reviewer's approvals are reset and reviewers must approve the new version. If
the content is edited after final approval, a banner appears on the document
indicating that the current version differs from the approved one.

The
approvals
resource includes a
Status
object that details the status
of the approval when the resource is requested. It also includes the
ReviewerResponse
object that
details the responses to an approval made by specific reviewers. Each reviewer's
response is represented by the
Response
object.

Every action in the approval process generates email notifications that are sent
to the initiator (the user requesting the approval) and all reviewers. It's also
added to the approval activity log.

All reviewers must approve an approval. Any reviewer declining an approval sets
the completed state to
DECLINED
.

After an approval is complete (the status is
APPROVED
,
CANCELLED
or
DECLINED
), it remains in the completed state and can't be interacted with by
the initiator or reviewers. You can add comments to a completed approval as long
as there's no existing approval on a file with a status of
IN_PROGRESS
.


### Lifecycle of an approval

An approval goes through several states during its lifecycle. Figure 1 shows the
high-level steps of an approval lifecycle:

- Start the approval
. Call
start
to begin the approval request. The
status
is then set to
IN_PROGRESS
.
Start the approval
. Call
start
to begin the approval request. The
status
is then set to
IN_PROGRESS
.

- Approval is pending
. While the approval is pending (
status
is set to
IN_PROGRESS
) both the initiator and reviewers can interact with it. They
can add a
comment
, the initiator
can
reassign
reviewers, and one
or more reviewers can
approve
the
request.
Approval is pending
. While the approval is pending (
status
is set to
IN_PROGRESS
) both the initiator and reviewers can interact with it. They
can add a
comment
, the initiator
can
reassign
reviewers, and one
or more reviewers can
approve
the
request.

- Approval is in the completed state
. An approval enters the completed
state (
status
is set to
APPROVED
,
CANCELLED
or
DECLINED
) when all
reviewers approve the request, the initiator elects to
cancel
the request, or if any reviewer chooses
to
decline
the request.
Approval is in the completed state
. An approval enters the completed
state (
status
is set to
APPROVED
,
CANCELLED
or
DECLINED
) when all
reviewers approve the request, the initiator elects to
cancel
the request, or if any reviewer chooses
to
decline
the request.


## Use the fields parameter

If you want to specify the fields to return in the response, you can set the
fields
system
parameter
with any method of the
approvals
resource. If you omit the
fields
parameter,
the server returns a default set of fields specific to the method. To return
different fields, see
Return specific fields
.


## Start and administer approvals

The
approvals
resource can be used to start
and manage approvals using Drive API. These methods work with any of
the existing OAuth 2.0 Drive API scopes that allow writing file
metadata. For more information, see
Choose Google Drive API scopes
.


### Start approval

To start a new approval on a file, use the
start
method on the
approvals
resource and include the
fileId
path parameter.

The
request body
consists of
a required
reviewerEmails
field that's an array of strings containing the
email addresses of the reviewers assigned to review the file. Each reviewer
email address must be associated with a Google Account or the request fails.
Additionally, three optional fields are offered:

- dueTime
: The deadline for the approval in RFC 3339 format.
- lockFile
: A boolean indicating whether to lock the file when starting the
approval. This blocks users from modifying the file during the approval
process. Any user with the
role=writer
permission can remove this lock.
- message
: A custom message sent to reviewers.
The response body contains an instance of the
approvals
resource and it
includes the
initiator
field
which is the user that requested the approval. The approval
Status
is set to
IN_PROGRESS
.

If an existing approval is present with a
Status
of
IN_PROGRESS
, the
start
method fails. You can only start an approval if there's no existing approval on
the file or if the existing approval is in the completed state (the status is
APPROVED
,
CANCELLED
or
DECLINED
).


### curl


```bash
curl
-X
POST
'https://www.googleapis.com/drive/v3/files/
FILE_ID
/approvals:start'
\
-H
'Authorization: Bearer
ACCESS_TOKEN
'
\
-H
'Content-Type: application/json'
\
-d
'{
"reviewerEmails": [
"reviewer1@example.com",
"reviewer2@example.com"
],
"dueTime": "2026-04-01T15:01:23Z",
"lockFile": true,
"message": "Please review this file for approval."
}'
```

Replace the following:

- FILE_ID
: The ID of the file the approval is on.
- ACCESS_TOKEN
: Your app's
OAuth
2.0
token.

### Comment on approval

To comment on an approval, use the
comment
method on the
approvals
resource and include the
fileId
and
approvalId
path parameters.

The
request body
consists
of a required
message
field that's a string containing the comment you want to
add to the approval.

The response body contains an instance of the
approvals
resource. The message
is sent to the approval initiator and reviewers as a notification, and it's also
included in the approval activity log.


```bash
curl
-X
POST
'https://www.googleapis.com/drive/v3/files/
FILE_ID
/approvals/
APPROVAL_ID
:comment'
\
-H
'Authorization: Bearer
ACCESS_TOKEN
'
\
-H
'Content-Type: application/json'
\
-d
'{
"message": "The required comment on the approval."
}'
```

- APPROVAL_ID
: The ID of the approval.

### Reassign reviewers on approval

To reassign reviewers on an approval, use the
reassign
method on the
approvals
resource and include the
fileId
and
approvalId
path parameters.

The
reassign
method lets the approval initiator (or a user with the
role=writer
permission) to add or replace reviewers in the
ReviewerResponse
object of
the
approvals
resource. A user with the
role=reader
permission can only
reassign an approval that's assigned to themselves. This lets the user reassign
a request to someone else who's a more capable reviewer.

Reviewers can only be reassigned while the
Status
is
IN_PROGRESS
and the
response
field for the reviewer being reassigned is set to
NO_RESPONSE
.

Note that you cannot remove a reviewer on an approval. If you need to remove a
reviewer, you must cancel the approval and start a new one.

The
request body
consists
of the optional
addReviewers
and
replaceReviewers
fields. Each field has a
repeated object for
AddReviewer
and
ReplaceReviewer
which each contain a single reviewer to add or a pair of reviewers to replace.
You can also add the optional
message
field containing the comment you want to
send to the new reviewers.

The response body contains an instance of the
approvals
resource. The message
is sent to the new reviewers as a notification, and it's also included in the
approval activity log.


```bash
curl
-X
POST
'https://www.googleapis.com/drive/v3/files/
FILE_ID
/approvals/
APPROVAL_ID
:reassign'
\
-H
'Authorization: Bearer
ACCESS_TOKEN
'
\
-H
'Content-Type: application/json'
\
-d
'{
"addReviewers": [
{
"addedReviewerEmail": "new_reviewer@example.com"
}
],
"replaceReviewers": [
{
"addedReviewerEmail": "replacement_reviewer@example.com",
"removedReviewerEmail": "old_reviewer@example.com"
}
],
"message": "Reassigning reviewers for this approval request."
}'
```

- ACCESS_TOKEN
: Your app's
OAuth
 2.0
token.

### Cancel approval

To cancel an approval, use the
cancel
method on the
approvals
resource and include
the
fileId
and
approvalId
path parameters.

The
cancel
method can only be called by the approval initiator (or a user with
the
role=writer
permission) while the approval
Status
is
IN_PROGRESS
.

The
request body
consists of
an optional
message
field that's a string containing the message to accompany
the cancellation of the approval.

The response body contains an instance of the
approvals
resource. The message
is sent as a notification, and it's also included in the approval activity log.
The approval
Status
is set to
CANCELLED
and it's in a completed state.


```bash
curl
-X
POST
'https://www.googleapis.com/drive/v3/files/
FILE_ID
/approvals/
APPROVAL_ID
:cancel'
\
-H
'Authorization: Bearer
ACCESS_TOKEN
'
\
-H
'Content-Type: application/json'
\
-d
'{
"message": "The optional reason for cancelling this approval request."
}'
```


### Decline approval

To decline an approval, use the
decline
method on the
approvals
resource and include the
fileId
and
approvalId
path parameters.

The
decline
method can only be called while the approval
Status
is
IN_PROGRESS
.

The
request body
consists of
an optional
message
field that's a string containing the message to accompany
the denial of the approval.

The response body contains an instance of the
approvals
resource. The message
is sent as a notification, and it's also included in the approval activity log.
The
response
field of the
ReviewerResponse
object of the requesting user is set to
DECLINED
. Additionally, the approval
Status
is set to
DECLINED
and it's in a completed state.


```bash
curl
-X
POST
'https://www.googleapis.com/drive/v3/files/
FILE_ID
/approvals/
APPROVAL_ID
:decline'
\
-H
'Authorization: Bearer
ACCESS_TOKEN
'
\
-H
'Content-Type: application/json'
\
-d
'{
"message": "The optional reason for declining this approval request."
}'
```


### Approve approval

To approve an approval, use the
approve
method on the
approvals
resource and include the
fileId
and
approvalId
path parameters.

The
approve
method can only be called while the approval
Status
is
IN_PROGRESS
.

The
request body
consists
of an optional
message
field that's a string containing the message to
accompany the approval.

The response body contains an instance of the
approvals
resource. The message
is sent as a notification, and it's also included in the approval activity log.
The
response
field of the
ReviewerResponse
object of the requesting user is set to
APPROVED
. Additionally, if this is the
last required reviewer response, the approval
Status
is set to
APPROVED
and
it's in a completed state.


```bash
curl
-X
POST
'https://www.googleapis.com/drive/v3/files/
FILE_ID
/approvals/
APPROVAL_ID
:approve'
\
-H
'Authorization: Bearer
ACCESS_TOKEN
'
\
-H
'Content-Type: application/json'
\
-d
'{
"message": "The optional reason for approving this approval request."
}'
```


## Locate existing approvals

The
approvals
resource can also be used to get
and list the status of your approvals using Drive API.

To view approvals on a file, you must have permission to read the metadata of
the file. For more information, see
Roles and
permissions
.


### Get approval

To get an approval on a file, use the
get
method on the
approvals
resource with the
fileId
and
approvalId
path
parameters. If you don't know the approval ID, you can
list
approvals
using the
list
method.

The response body contains an instance of the
approvals
resource.


```bash
curl
-X
GET
'https://www.googleapis.com/drive/v3/files/
FILE_ID
/approvals/
APPROVAL_ID
'
\
-H
'Authorization: Bearer
ACCESS_TOKEN
'
\
-H
'Accept: application/json'
```


### List approvals

To list approvals on a file, call the
list
method on the
approvals
resource
and include the
fileId
path parameter.

The
response body
consists of
a list of approvals on the file. The
items
field includes information about each approval in the form of an
approvals
resource.

You can also pass the following query parameters to customize pagination of, or
filter, the approvals:

- pageSize
: The maximum number of approvals to return per page. If you don't
set
pageSize
, the server returns up to 100 approvals.
pageSize
: The maximum number of approvals to return per page. If you don't
set
pageSize
, the server returns up to 100 approvals.

- pageToken
: A page token, received from a previous list call. This token is
used to retrieve the subsequent page. It should be set to the value of
nextPageToken
from a previous response.
pageToken
: A page token, received from a previous list call. This token is
used to retrieve the subsequent page. It should be set to the value of
nextPageToken
from a previous response.


```bash
curl
-X
GET
'https://www.googleapis.com/drive/v3/files/
FILE_ID
/approvals?pageSize=10'
\
-H
'Authorization: Bearer
ACCESS_TOKEN
'
\
-H
'Accept: application/json'
```


## Related topics

- Roles and permissions
- Manage approvals as an administrator
- Get approvals on files in Google Drive
Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2026-04-23 UTC.


---

# Changes and revisions overview Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/guides/change-overview

- Home
- Google Workspace
- Google Drive
- Guides
Google Drive maintains an automatic history of modifications, which can help
users track file changes and content revisions. In the revision history, users
can see what edits have been made and can revert to a specific version of a file
with specific edits.

The following terms are relevant to the changes and revisions resources of the
Google Drive API:

A record of all changes that a user made to every editable file in their My
Drive, such as a Google Docs, Sheets, or a
Slides. For members of a shared drive, the user change log
also includes entries about shared drive membership, user access levels to
items in that shared drive, and shared drive name changes.

A record of all changes to a shared drive, such as additions or removals of
users, and all changes to items on that shared drive. A change to an item
within a shared drive appears in both the
user change log
and shared drive
change log.

A record of a change made to a file's content or metadata of a file or shared
drive. A change log entry indicates the user who made the change, the
timestamp, and an ID. There can only be one entry per file or shared drive
in the change log at a time. Each time that file or shared drive changes, a
new ID is created for that entry, and it replaces the previous entry.

A version of the file representing a change to the file's contents (not
metadata). Each revision can be accessed using the
revisions
resource within the Drive API.

The most current version of a file. The
headRevisionId
can be accessed using
the
files
resource within the
Drive API. The
headRevisionId
is only available for blob files
in Drive.

A version of an unmodifiable binary file, such as an image, video, or PDF. If
the blob revision is the only revision of the binary file, it cannot be
deleted. A new blob can be uploaded as a new
revision
, which becomes the
new
head revision
of that file.

Any blob file revision, other than the head revision, that's not designated
as "Keep Forever" is purgeable. Purgeable revisions are typically preserved
for 30 days, but can be purged earlier if a file has 100 revisions that
aren't designated as "Keep Forever" and a new revision is uploaded.

For more information on setting blob revisions as "Keep Forever", see
Specify revisions to save from auto
delete
.

A record of all revisions of a file in chronological order. A change to a
Docs, Sheets, or Slides file
gets a new revision. Each time the content changes, Drive
creates a new revision history entry for that file. However, these editor
file revisions may be merged together, so the API response might not show
all changes to a file.


## Related topics

- To identify where the change you want to track is recorded, see
Identify
which change log to track
.
- To set up change tracking for users and shared drives, see
Track changes
for users and shared drives
.
- To download a blob file content revision or to export a Google Workspace
document content revision, see
Download and export
files
.
- To publish a revision, see
Manage file
revisions
.
- To set up change notifications, see
Notifications for resource changes
.
Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2026-04-20 UTC.


---

# Protect file content Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/guides/content-restrictions

- Home
- Google Workspace
- Google Drive
- Guides
The Google Drive API supports several ways to prevent file modification, including
file content restriction and prohibiting the option to download, print, or copy
files.


## Make files read-only with Drive content restrictions

You can add a content restriction to a Google Drive file to prevent users from
doing the following:

- Modifying the title
- Making content edits
- Uploading a revision
- Adding or modifying comments
A content restriction isn't an access restriction. While users cannot modify the
file's content, other operations are still allowed, based on their access level.
For example, a user with edit access can still move an item or change its
sharing settings.

To add or remove a content restriction on a file in Drive, a user
must have the associated
permissions
. For a
file or folder in My Drive or a shared drive with the
capabilities.canModifyEditorContentRestriction
, you must have
role=writer
assigned. For a file or folder in My Drive or a shared drive with
an
ownerRestricted
content restriction, you must own the file or have
role=organizer
. To view an item with a content restriction, users must have
role=reader
or higher. For a complete list of roles, see
Roles and
permissions
. To update permissions on a file, see
Update permissions
.

You can use the
contentRestrictions.readOnly
boolean field on the
files
resource to set a content
restriction. Note that setting a content restriction on an item overwrites the
existing one.


### Scenarios for content restrictions

A content restriction on a Drive item signals to users that the
contents shouldn't be changed. This can be for some of the following reasons:

- Pausing work on a collaborative document during review or audit periods.
- Setting an item to a finalized state, such as approved.
- Preventing changes during a sensitive meeting.
- Prohibiting external changes for workflows handled by automated systems.
- Restricting edits by Google Apps Script and Google Workspace add-ons.
- Avoiding accidental edits to a document.
Note though that while content restrictions can help manage content, it's not
meant to prevent users with sufficient permissions from continuing to work on an
item. Additionally, it isn't a way to create an immutable record.
Drive content restrictions are mutable, so a content restriction
on an item doesn't guarantee that the item never changes.


### Manage files with content restrictions

Google Docs, Google Sheets, and Google Slides, as well as all other files,
can contain content restrictions.

A content restriction on an item prevents changes to its title and content,
including:

- Comments and suggestions (on Docs, Sheets,
Slides, and binary files)
- Revisions of a binary file
- Text and formatting in Docs
- Text or formulas in Sheets, a Sheets layout,
and instances in Sheets
- All content in Slides, as well as the order and number of the
slides
Certain file types can't contain a content restriction. A few examples are:

- Google Forms
- Google Sites
- Google Drawings
- Shortcuts and third-party shortcuts. For more information, see
Create a
shortcut file to content stored by your
app
and
Create a shortcut to a
Drive file
.

### Add a content restriction

To add a file content restriction, use the
files.update
method with the
contentRestrictions.readOnly
field set to
true
. Add an optional
reason
for
why you're adding the restriction, such as "Finalized contract." The following
code sample shows how to add a content restriction:


### Java


```
File
updatedFile
=
new
File
()
.
setContentRestrictions
(
ImmutableList
.
of
(
new
ContentRestriction
().
setReadOnly
(
true
).
setReason
(
"Finalized contract."
));
File
response
=
driveService
.
files
().
update
(
"
FILE_ID
"
,
updatedFile
).
setFields
(
"contentRestrictions"
).
execute
();
```


### Python


```
content_restriction
=
{
'readOnly'
:
True
,
'reason'
:
'Finalized contract.'
}
response
=
drive_service
.
files
()
.
update
(
fileId
=
"
FILE_ID
"
,
body
=
{
'contentRestrictions'
:
[
content_restriction
]},
fields
=
"contentRestrictions"
)
.
execute
();
```


### Node.js


```
/**
* Set a content restriction on a file.
* @return{obj} updated file
**/
async
function
addContentRestriction
()
{
// Get credentials and build service
// TODO (developer) - Use appropriate auth mechanism for your app
const
{
GoogleAuth
}
=
require
(
'google-auth-library'
);
const
{
google
}
=
require
(
'googleapis'
);
const
auth
=
new
GoogleAuth
({
scopes
:
'https://www.googleapis.com/auth/drive'
});
const
service
=
google
.
drive
({
version
:
'v3'
,
auth
});
const
contentRestriction
=
{
'readOnly'
:
True
,
'reason'
:
'Finalized contract.'
,
};
const
updatedFile
=
{
'contentRestrictions'
:
[
contentRestriction
],
};
try
{
const
response
=
await
service
.
files
.
update
({
fileId
:
'
FILE_ID
'
,
resource
:
updatedFile
,
fields
:
'contentRestrictions'
,
});
return
response
;
}
catch
(
err
)
{
// TODO (developer) - Handle error
throw
err
;
}
}
```

Replace
FILE_ID
with the
fileId
of the file that you want to
modify.

When you run the sample code, the file is content restricted and a lock symbol
(
lock
) appears beside the filename within
the
Google Drive user interface
(UI)
. The file is now read-only.


### Remove a content restriction

To remove a file content restriction, use the
files.update
method with the
contentRestrictions.readOnly
field set to
false
. The following code sample
shows how to remove a content restriction:


```
File
updatedFile
=
new
File
()
.
setContentRestrictions
(
ImmutableList
.
of
(
new
ContentRestriction
().
setReadOnly
(
false
));
File
response
=
driveService
.
files
().
update
(
"
FILE_ID
"
,
updatedFile
).
setFields
(
"contentRestrictions"
).
execute
();
```


```
content_restriction
=
{
'readOnly'
:
False
}
response
=
drive_service
.
files
()
.
update
(
fileId
=
"
FILE_ID
"
,
body
=
{
'contentRestrictions'
:
[
content_restriction
]},
fields
=
"contentRestrictions"
)
.
execute
();
```


```
/**
* Remove a content restriction on a file.
* @return{obj} updated file
**/
async
function
removeContentRestriction
()
{
// Get credentials and build service
// TODO (developer) - Use appropriate auth mechanism for your app
const
{
GoogleAuth
}
=
require
(
'google-auth-library'
);
const
{
google
}
=
require
(
'googleapis'
);
const
auth
=
new
GoogleAuth
({
scopes
:
'https://www.googleapis.com/auth/drive'
});
const
service
=
google
.
drive
({
version
:
'v3'
,
auth
});
const
contentRestriction
=
{
'readOnly'
:
False
,
};
const
updatedFile
=
{
'contentRestrictions'
:
[
contentRestriction
],
};
try
{
const
response
=
await
service
.
files
.
update
({
fileId
:
'
FILE_ID
'
,
resource
:
updatedFile
,
fields
:
'contentRestrictions'
,
});
return
response
;
}
catch
(
err
)
{
// TODO (developer) - Handle error
throw
err
;
}
}
```

When you run the sample code, the file is no longer content restricted.

You can also use the Drive UI to remove a content restriction and
allow content editing (provided you have the correct permissions). There are two
options to do this:

- In Drive, right-click the file with a content restriction and
click
Unlock
lock_open
.
Figure 2.
Remove a file content restriction within a Drive file list.
In Drive, right-click the file with a content restriction and
click
Unlock
lock_open
.

- Open the file with a content restriction and click
(Locked mode)
lock
>
Unlock file
.
Figure 3.
Remove a file content restriction within a document.
Open the file with a content restriction and click
(Locked mode)
lock
>
Unlock file
.


### Check for a content restriction

To check for a content restriction, use the
files.get
method with the
contentRestrictions
returned field. The following code sample shows how to
check the status of a content restriction:


```
File
response
=
driveService
.
files
().
get
(
"
FILE_ID
"
).
setFields
(
"contentRestrictions"
).
execute
();
```


```
response
=
drive_service
.
files
()
.
get
(
fileId
=
"
FILE_ID
"
,
fields
=
"contentRestrictions"
)
.
execute
();
```


```
/**
* Get content restrictions on a file.
* @return{obj} updated file
**/
async
function
fetchContentRestrictions
()
{
// Get credentials and build service
// TODO (developer) - Use appropriate auth mechanism for your app
const
{
GoogleAuth
}
=
require
(
'google-auth-library'
);
const
{
google
}
=
require
(
'googleapis'
);
const
auth
=
new
GoogleAuth
({
scopes
:
'https://www.googleapis.com/auth/drive'
});
const
service
=
google
.
drive
({
version
:
'v3'
,
auth
});
try
{
const
response
=
await
service
.
files
.
get
({
fileId
:
'
FILE_ID
'
,
fields
:
'contentRestrictions'
,
});
return
response
;
}
catch
(
err
)
{
// TODO (developer) - Handle error
throw
err
;
}
}
```

Replace
FILE_ID
with the
fileId
of the file that you want to
check.

When you run the sample code, the method returns a
ContentRestriction
resource if present.


### Add a content restriction only the file owner can modify

To add a file content restriction so only file owners can toggle the mechanism,
use the
files.update
method with the
contentRestrictions.ownerRestricted
boolean field set to
true
. The following
code sample shows how to add a content restriction for file owners only:


```
File
updatedFile
=
new
File
()
.
setContentRestrictions
(
ImmutableList
.
of
(
new
ContentRestriction
().
setReadOnly
(
true
).
setOwnerRestricted
(
true
).
setReason
(
"Finalized contract."
));
File
response
=
driveService
.
files
().
update
(
"
FILE_ID
"
,
updatedFile
).
setFields
(
"contentRestrictions"
).
execute
();
```


```
content_restriction
=
{
'readOnly'
:
True
,
'ownerRestricted'
:
True
,
'reason'
:
'Finalized contract.'
}
response
=
drive_service
.
files
()
.
update
(
fileId
=
"
FILE_ID
"
,
body
=
{
'contentRestrictions'
:
[
content_restriction
]},
fields
=
"contentRestrictions"
)
.
execute
();
```


```
/**
* Set an owner restricted content restriction on a file.
* @return{obj} updated file
**/
async
function
addOwnerRestrictedContentRestriction
()
{
// Get credentials and build service
// TODO (developer) - Use appropriate auth mechanism for your app
const
{
GoogleAuth
}
=
require
(
'google-auth-library'
);
const
{
google
}
=
require
(
'googleapis'
);
const
auth
=
new
GoogleAuth
({
scopes
:
'https://www.googleapis.com/auth/drive'
});
const
service
=
google
.
drive
({
version
:
'v3'
,
auth
});
const
contentRestriction
=
{
'readOnly'
:
True
,
'ownerRestricted'
:
True
,
'reason'
:
'Finalized contract.'
,
};
const
updatedFile
=
{
'contentRestrictions'
:
[
contentRestriction
],
};
try
{
const
response
=
await
service
.
files
.
update
({
fileId
:
'
FILE_ID
'
,
resource
:
updatedFile
,
fields
:
'contentRestrictions'
,
});
return
response
;
}
catch
(
err
)
{
// TODO (developer) - Handle error
throw
err
;
}
}
```

When you run the sample code, the file is content restricted and only file
owners can remove it. If you're the file owner, an active lock symbol (
lock
) appears beside the filename within the
Drive user interface
(UI)
. If you're not the owner, the
lock symbol is dimmed.

To remove the
ownerRestricted
flag, use the
files.update
method with the
contentRestrictions.ownerRestricted
field set to
false
.


### Content restriction capabilities

A
files
resource contains a collection of boolean
capabilities
fields used to indicate whether an action can be performed on a
file.

Content restrictions contain the following
capabilities
:

- capabilities.canModifyEditorContentRestriction
: Whether the current user
can add or modify a
content restriction
.
- capabilities.canModifyOwnerContentRestriction
: Whether the current user
can add or modify an
owner content restriction
.
- capabilities.canRemoveContentRestriction
: Whether the current user can
remove the applied
content restriction
(if present).
For more information, see
Understand file
capabilities
.

For an example of retrieving file
capabilities
, see
Get file capabilities
.


## Prevent users from downloading, printing, or copying your file

You can limit how users can download, print, and copy files within
Drive, Docs, Sheets, and
Slides.

To determine whether the user can change owner or organizer-applied download
restrictions of a file, check the
capabilities.canChangeItemDownloadRestriction
boolean field. If
capabilities.canChangeItemDownloadRestriction
is set to
true
, download
restrictions can be applied to the file. For more information, see
Understand
file capabilities
.

To apply download restrictions to a file, set the
downloadRestrictions
field using the
files.update
method. You can set the field
using the
DownloadRestrictionsMetadata
object.

The
DownloadRestrictionsMetadata
object has two fields:
itemDownloadRestriction
and
effectiveDownloadRestrictionWithContext
. Both
fields are readable but only the
itemDownloadRestriction
can be set. The
itemDownloadRestriction
field returns a
DownloadRestriction
object. The
DownloadRestriction
object has two separate boolean fields:
restrictedForReaders
and
restrictedForWriters
.

When setting the
itemDownloadRestriction
field the download restriction of the
file is applied directly by the owner or organizer. It doesn't account for
shared drive settings or data loss prevention (DLP) rules. For more information,
see
About DLP
.

If you update the
itemDownloadRestriction
field by setting the
restrictedForWriters
field to
true
, it implies that
restrictedForReaders
is
true
. Similarly, setting
restrictedForWriters
to
true
and
restrictedForReaders
to
false
is equivalent to setting both
restrictedForWriters
and
restrictedForReaders
to
true
.

For the
effectiveDownloadRestrictionWithContext
field the download restriction
is applied to the file and it accounts for all restriction settings and DLP
rules.

The
effectiveDownloadRestrictionWithContext
field can be set to either
restrictedForWriters
or
restrictedForReaders
. If there's any download or
copy restriction settings for the corresponding roles from file settings, shared
drive settings, or DLP rules (including those ones with context), then the value
is set to
true
, otherwise it's
false
.


### Backward compatibility

We recommend that you use the
DownloadRestriction
object to
enforce how users can download, print, and copy files.

If you want to use the
copyRequiresWriterPermission
boolean field, the functionality is different for both reading from and writing
to the field.

The retrieved value of the
copyRequiresWriterPermission
field reflects whether
users with the
role=commenter
or
role=reader
permission can download, print,
or copy files within Drive. The field value reflects the
combination of file settings, shared drive settings, or DLP rules. However,
context evaluation for DLP rules isn't included.

Setting the
copyRequiresWriterPermission
field to
false
updates both the
restrictedForWriters
and
restrictedForReaders
fields to
false
. This means
download or copy restriction settings are removed for all users.


### Fields that control download, print, and copy features

The following table lists
files
resource fields
that affect download, print, and copy functionality:


| Field | Description | Version |
| --- | --- | --- |
| capabilities.canCopy | Whether the current user can copy a file. | v2 & v3 |
| capabilities.canDownload | Whether the current user can download a file. | v2 & v3 |
| capabilities.canChangeCopyRequiresWriterPermission | Whether the current user can change the
copyRequiresWriterPermission
restriction of a file. | v2 & v3 |
| capabilities.canChangeItemDownloadRestriction | Whether the current user can change the download restriction of a file. | v3 only |
| copyRequiresWriterPermission | Whether the options to copy, print, or download this file, should be disabled for readers and commenters. | v2 & v3 |
| downloadRestrictions | The download restrictions applied on a file. | v3 only |


## Related topics

- Roles and permissions
Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2026-04-20 UTC.


---

# Create and manage files Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/guides/create-file

- Home
- Google Workspace
- Google Drive
- Guides
This guide explains how to create and manage files in Google Drive using the
Google Drive API.


## Create file

To create a file in Drive that contains no metadata or content,
use the
create
method on the
files
resource with no parameters.

When you create the file, the method returns a
files
resource. The file is
given a
kind
of
drive.file
, an
id
, a
name
of "Untitled", and a
mimeType
of
application/octet-stream
. The
uploadType
is marked as required but defaults to
media
, so you don't actually have to
supply it.

For more information about Drive file limits, see
File and
folder limits
.


## Use the fields parameter

If you want to specify the fields to return in the response, you can set the
fields
system
parameter
with any method of the
files
resource. If you omit the
fields
parameter, the
server returns a default set of fields specific to the method. For example, the
list
method returns only the
kind
,
id
,
name
,
mimeType
, and
resourceKey
fields for each file. To return different
fields, see
Return specific fields
.


## File ownership

When a file is created using the Drive API, ownership depends on the
authentication credentials used by the app in the following ways:

- User account (OAuth 2.0)
: If the application authenticates on behalf of
a user, that user becomes the file owner. The file then resides in their My
Drive folder or a
specified
folder
. It consumes their storage quota.
User account (OAuth 2.0)
: If the application authenticates on behalf of
a user, that user becomes the file owner. The file then resides in their My
Drive folder or a
specified
folder
. It consumes their storage quota.

- Service Account
: If the application authenticates using a Service
Account, the Service Account is the file owner. The file then resides in the
Service Account's dedicated Drive storage. Files don't appear
within other Drive storage accounts unless explicitly shared.
If the Service Account is deleted, all files it owns are deleted
immediately.
If you're using a Service Account but want a specific user account to own a
file, use Domain-Wide Delegation. This allows the Service Account to
impersonate a user and to create files on their behalf. For more
information, see
Delegate domain-wide authority to the service
account
.
Service Account
: If the application authenticates using a Service
Account, the Service Account is the file owner. The file then resides in the
Service Account's dedicated Drive storage. Files don't appear
within other Drive storage accounts unless explicitly shared.
If the Service Account is deleted, all files it owns are deleted
immediately.

If you're using a Service Account but want a specific user account to own a
file, use Domain-Wide Delegation. This allows the Service Account to
impersonate a user and to create files on their behalf. For more
information, see
Delegate domain-wide authority to the service
account
.

For more information about file permissions, see
Share files, folders, and
drives
.


## Generate IDs to use with your files

The
generateIds
method on the
files
resource lets you pre-generate unique file
IDs that can be used when creating or copying files and folders in
Drive. This can be useful when you need to control the file IDs
from your app, rather than letting Drive assign them
automatically.

You can set the number of IDs generated using the
count
query parameter.
If
count
is not set, 10 are returned by default. The maximum number of IDs you
can request is capped at 1,000.

You can also designate the
space
in which the IDs
can be used and the
type
of items which the
IDs can be used for.

Once an ID is generated, it can be passed to the
create
or
copy
method
through the
id
field. This ensures that the created or copied file uses the
predetermined ID.

If the file is successfully created or copied, subsequent retries return a
409
Conflict
HTTP status code response and duplicate files aren't created.

Note that pre-generated IDs aren't supported for the creation of
Google Workspace files, except for the
application/vnd.google-apps.drive-sdk
and
application/vnd.google-apps.folder
MIME
types
. Similarly, uploads referencing a conversion
to a Google Workspace file format aren't supported.


## Create metadata-only files

Metadata-only files contain no content. Metadata is data (such as
name
,
mimeType
, and
createdTime
) that describes the file. Fields like
name
are
user-agnostic and appear the same for each user, whereas fields such as
viewedByMeTime
contain user-specific values.

One example of a metadata-only file is a folder with the MIME type
application/vnd.google-apps.folder
. For more information, see
Create and
populate folders
. Another example is a shortcut that
points to another file on Drive with the MIME type
application/vnd.google-apps.shortcut
. For more information, see
Create a
shortcut to a Drive file
.


## Manage thumbnail images

Thumbnails help users identify Drive files. Drive
can automatically generate thumbnails for common file types or you can provide a
thumbnail image generated by your app. For more information, see
Upload
thumbnails
.


## Copy an existing file

To copy a file, and apply any requested updates, use the
copy
method on the
files
resource. To find the
fileId
to copy, use the
list
method.

You can apply updates through patch semantics, meaning you can make partial
modifications to a resource. You must explicitly set the fields that you intend
to modify in your request. Any fields not included in the request retain their
existing values. For more information, see
Working with partial resources
.

You can pre-set the file ID of the copied file using the
generateIds
method. For more information, see
Generate IDs to use with your files
.

Note that you need to use an appropriate
Drive API
scope
to authorize the
call. For more information on Drive scopes, see
Choose
Google Drive API scopes
.


### Limits and considerations

As you prepare to copy files, take note of these limits and considerations:

- Permissions
:
The
DownloadRestrictionsMetadata
object of the
files
resource determines
who can copy the file. For more information, see
Prevent users from
downloading, printing, or copying your
file
.
The
capabilities.canCopy
field resource determines whether the user can copy a file. For more
information, see
Understand file
capabilities
.
The user that created the copy owns the copied file. No other sharing
settings from the source file are replicated. If the copy is created in
a shared folder, it inherits the permissions of that folder.
A copied file's ownership might change and the copy might not inherit
the original file's sharing settings. These settings might need to be
reset.
Permissions
:

- The
DownloadRestrictionsMetadata
object of the
files
resource determines
who can copy the file. For more information, see
Prevent users from
downloading, printing, or copying your
file
.
- The
capabilities.canCopy
field resource determines whether the user can copy a file. For more
information, see
Understand file
capabilities
.
- The user that created the copy owns the copied file. No other sharing
settings from the source file are replicated. If the copy is created in
a shared folder, it inherits the permissions of that folder.
- A copied file's ownership might change and the copy might not inherit
the original file's sharing settings. These settings might need to be
reset.
- File management
:
Some files, like
third-party
shortcuts
, can never be copied.
You can only copy a file into one parent folder. Specifying multiple
parents isn't supported. If the
parents
field isn't
specified, the file inherits any discoverable parents from the source
file.
Even though a folder is a type of file, you can't copy a folder.
Instead, create a destination folder and set the
parents
field of the
existing files to the destination folder. You can then delete the
original source folder.
Unless a new filename is specified, the
copy
method produces a file
with the same name as the original.
Excessive use of
copy
can lead to exceeding your Drive API
quota limits. For more information, see
Usage
limits
.
File management
:

- Some files, like
third-party
shortcuts
, can never be copied.
- You can only copy a file into one parent folder. Specifying multiple
parents isn't supported. If the
parents
field isn't
specified, the file inherits any discoverable parents from the source
file.
- Even though a folder is a type of file, you can't copy a folder.
Instead, create a destination folder and set the
parents
field of the
existing files to the destination folder. You can then delete the
original source folder.
- Unless a new filename is specified, the
copy
method produces a file
with the same name as the original.
- Excessive use of
copy
can lead to exceeding your Drive API
quota limits. For more information, see
Usage
limits
.

## Related topics

Here are a few next steps you might try:

- To upload file data when you create or update a file, see
Upload file
data
.
To upload file data when you create or update a file, see
Upload file
data
.

- To create a file in a specific folder, see
Create a file in a specific
folder
.
To create a file in a specific folder, see
Create a file in a specific
folder
.

- To move files, see
Move files between
folders
.
To move files, see
Move files between
folders
.

- To work with file metadata, see
Manage file metadata
.
To work with file metadata, see
Manage file metadata
.

- To delete a file, see
Trash or delete files and
folders
.
To delete a file, see
Trash or delete files and
folders
.

Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2026-04-20 UTC.


---

# Trash or delete files and folders Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/guides/delete

- Home
- Google Workspace
- Google Drive
- Guides
You can remove Google Drive files and folders from both your My
Drive and shared drives. You have two options to do this: trash
or delete.

You can move files and folders into the trash and then restore them (within 30
days of trashing them). Deleting files and folders removes them permanently from
Drive. If you trash, restore, or permanently delete multiple
files or folders at once, it might take time for you to notice the changes.

This guide explains how you can dispose of files in Drive.


## Use the fields parameter

If you want to specify the fields to return in the response, you can set the
fields
system
parameter
with any method of the
files
resource. If you omit the
fields
parameter, the
server returns a default set of fields specific to the method. For example, the
list
method returns only the
kind
,
id
,
name
,
mimeType
, and
resourceKey
fields for each file. To return different
fields, see
Return specific fields
.


## Trash

To remove Drive files, you can move them to the trash. Files in
the trash are automatically deleted after 30 days. You can restore files from
your trash before the 30-day period.

Only the file owner can trash a file, but other users can still access the file
in the owner's trash until it's permanently deleted. If you attempt to trash a
file you don't own, you receive an
insufficientFilePermissions
error. For more
information, see
Permissions
.

To verify you're the file owner, call the
get
method on the
files
resource with the
fileId
path parameter and the
fields
parameter set to the boolean
ownedByMe
field. The
ownedByMe
field
isn't populated for files in shared drives because they're owned by the shared
drive, not individual users. For more information about the
fields
parameter,
see
Use the fields parameter
.

If you're not the file owner but still want a copy of the trashed file, do one
of the following:

- Make a copy of the file.
- Contact the owner to have them restore it from the trash.

### Move a file to the trash

To move a file to the trash, use the
update
method on the
files
resource with the
fileId
path parameter and set the boolean
trashed
field to
true
. To
trash a shared drive file, you must also set the boolean
supportsAllDrives
query
parameter to
true
. For more information, see
Implement shared drive
support
.

If successful, the
response
body
contains an instance of the
files
resource.

The following code sample shows how to use the
fileId
to mark the file as
trashed:


### Python


```
body_value
=
{
'trashed'
:
True
}
response
=
drive_service
.
files
()
.
update
(
fileId
=
"
FILE_ID
"
,
body
=
body_value
)
.
execute
()
```


### Node.js


```
const
body_value
=
{
'trashed'
:
true
};
const
response
=
await
drive_service
.
files
.
update
({
fileId
:
'
FILE_ID
'
,
requestBody
:
body_value
,
});
return
response
;
```

Replace
FILE_ID
with the
fileId
of the file that you want to
trash.


### Determine a trashed file's properties

When a file is trashed, you can retrieve additional file properties. You can use
the
get
method on the
files
resource with the
fileId
path parameter and use one
of the following trashed fields in the
fields
parameter. For more information
about the
fields
parameter, see
Use the fields parameter
.

The following fields are populated for all files:

- trashed
: Whether the file
was trashed, either explicitly or from a trashed parent folder. Note that
while using
trashed
with the
update
method sets the file's status, the
get
method retrieves the file's status.
- explicitlyTrashed
:
Whether the file was explicitly trashed, as opposed to recursively trashed,
from a parent folder.
The following fields are only populated for files located within a shared drive:

- trashedTime
: The time
that the item was trashed in
RFC
3339
date-time format. If
you're using the previous Drive API v2 version, this field is
called
trashedDate
.
- trashingUser
: If the
file was explicitly trashed, the user who trashed it.

### Recover a file from the trash

To recover a file from the trash, use the
update
method on the
files
resource with the
fileId
path parameter and set the
boolean
trashed
field to
false
. To untrash a shared drive file, you also must set the boolean
supportsAllDrives
query
parameter to
true
. For more information, see
Implement shared drive
support
.

The following code sample shows how to use the
fileId
to mark the file as
untrashed:


```
body_value
=
{
'trashed'
:
False
}
response
=
drive_service
.
files
()
.
update
(
fileId
=
"
FILE_ID
"
,
body
=
body_value
)
.
execute
()
```


```
const
body_value
=
{
'trashed'
:
false
};
const
response
=
await
drive_service
.
files
.
update
({
fileId
:
'
FILE_ID
'
,
requestBody
:
body_value
,
});
return
response
;
```

Replace
FILE_ID
with the
fileId
of the file that you want to
untrash.


## Empty trash

You can permanently delete all Drive files the user has
moved to
the trash
using the
emptyTrash
method on the
files
resource. To empty the trash of a shared drive, you
must also set the
driveId
query parameter to the shared drive ID.

If successful, the
response
body
contains an empty JSON
object.

The following code sample shows how to use the
fileId
to permanently delete
all files in the trash:


```
response
=
drive_service
.
files
()
.
emptyTrash
()
.
execute
()
```


```
const
response
=
await
drive_service
.
files
.
emptyTrash
({
});
return
response
;
```


## Delete

You can permanently delete a Drive file without moving it to the
trash. After you delete a file, anyone you've shared the file with loses access
to it. If you want others to retain access to the file, you can
transfer
ownership
to someone else before deletion.

To delete a shared drive file, the user must have
role=organizer
on the parent
folder. If you're deleting a folder, all descendants owned by the user are also
deleted. For more information, see
Permissions
.

To permanently delete a user-owned file without moving it to the trash, use the
delete
method on the
files
resource. To delete a shared drive file, you must also
set the boolean
supportsAllDrives
query
parameter to
true
. For more information, see
Implement shared drive
support
.

The following code sample shows how to use the
fileId
to delete the file:


```
response
=
drive_service
.
files
()
.
delete
(
fileId
=
"
FILE_ID
"
)
.
execute
()
```


```
const
response
=
await
drive_service
.
files
.
delete
({
fileId
:
'
FILE_ID
'
});
return
response
;
```

Replace
FILE_ID
with the
fileId
of the file that you want to
delete.


## Permissions

The following table shows the role permissions required to trash or delete files
and folders. For a complete list of roles and the operations permitted by each,
refer to
Roles and permissions
.


| Permitted operation | owner | organizer | fileOrganizer | writer | commenter | reader |
| --- | --- | --- | --- | --- | --- | --- |
| Move files and folders into the trash |  |  |  |  |  |  |
| Recover files and folders from the trash |  |  |  |  |  |  |
| Empty the trash |  |  |  |  |  |  |
| Delete a file or folder |  |  |  |  |  |  |
| Delete files and folders in a shared drive
[*] |  |  |  |  |  |  |
| Delete an empty shared drive |  |  |  |  |  |  |


### Capabilities

A
files
resource contains a collection of boolean
capabilities
fields that indicate the capabilities the user has on this file.

To check the capabilities, call the
get
method
on the
files
resource with the
fileId
path parameter and use one of the
following
capabilities
fields in the
fields
parameter. For more information about the
fields
parameter, see
Use the fields parameter
.

- capabilities.canTrash
:
Whether the current user can move this file to trash.
- capabilities.canUntrash
:
Whether the current user can restore this file from trash.
- capabilities.canDelete
:
Whether the current user can delete this file.
- capabilities.canRemoveChildren
:
Whether the current user can remove children from this folder. This is
false
when the item isn't a folder.
- capabilities.canTrashChildren
:
Whether the current user can trash children of this folder. This is
false
when the item isn't a folder.
- capabilities.canDeleteChildren
:
Whether the current user can delete children of this folder. This is
false
when the item isn't a folder.

## File and folder limits

Drive files and folders, along with shared drive folders, have
some storage limits.

Generally, after the item limit is reached, the only way to create more space is
to
permanently delete
items or use a
different account. Moving files to the trash isn't enough to free up space.

For more information on file and folder limits, see the following:

- File and folder limits in files
- Folder limits in shared drives

## Related topics

- Delete files in Google Drive
- Shared drive versus My Drive API differences
- Roles and permissions
Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2026-04-20 UTC.


---

# Install the Google Drive client libraries Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/guides/downloads

- Home
- Google Workspace
- Google Drive
- Reference
The Google Drive API is built on HTTP and JSON, so any standard HTTP client can
send requests to it and parse the responses.

However, the Google API client libraries provide better language integration,
improved security, and facilitate making calls that require user authorization.
The client libraries use each supported language's natural conventions and
reduce boilerplate code that you have to write. The client libraries are
available in several programming languages. By using them you can avoid the need
to manually set up HTTP requests and parse the responses.

Read more about the Cloud Client Libraries and the older Google API Client
Libraries in
Client libraries and Cloud APIs
explained
.


## Client libraries

Drive provides client libraries for the following languages.
Select the programming language that you want to use.


### Dart

Get the latest
Google Drive API client library for
Dart
.

Run the following command to install this client library in your environment
for Dart:


```
dart
pub
add
googleapis
```

Run the following command to install this client library in your environment
for Flutter:


```
flutter
pub
add
googleapis
```


### Code samples

To view or get individual code samples, see the
googleapis.dart
GitHub repository.


### Client library documentation

For more information, view the
client library
documentation
.


### Go

Get the latest
Google Drive API client library for
Go
.

Run the following command to install an API and a version of that API in
your environment:


```
go
get
google
.
golang
.
org
/
api
/
urlshortener
/
v1
```

To view or get individual code samples, see the
google-api-go-client
GitHub repository.


### Java

Get the latest
Google Drive API client library for
Java
.

To use Maven, add the following lines to your
pom.xml
file:


```
<
project
>
<
dependencies
>
<
dependency
>
<
groupId>com
.
google
.
apis
<
/
groupId
>
<
artifactId>google
-
api
-
services
-
drive
<
/
artifactId
>
<
version>v3
-
rev20240509
-
2.0.0
<
/
version
>
<
/
dependency
>
<
/
dependencies
>
<
/
project
>
```

To use Gradle, add the following lines to your
build.gradle
file:


```
repositories
{
mavenCentral
()
}
dependencies
{
implementation
'
com
.
google
.
apis
:
google
-
api
-
services
-
drive
:
v3
-
rev20240509
-
2.0.0
'
}
```

To view or get individual code samples, see the
google-api-java-client-services
GitHub repository.


### JavaScript

Get the latest
Google Drive API client library for
JavaScript
.

Use
gapi.client.request
to make requests to the JavaScript client library.

To view or get individual code samples, see the
google-api-javascript-client
GitHub repository.


### .NET

Get the latest
Google Drive API client library for
.NET
.

Run the following command to install this package in your environment:


```
dotnet
add
package
Google
.
Apis
--
version
1.68.0
```

For alternative methods of installation, see the
Google.Apis
NuGet page.

To view or get individual code samples, see the
Get
started
page.


### Node.js

Get the latest
Google Drive API client library for
Node.js
.

Run the following command to install this client library in your
environment:


```
npm
install
@
googleapis
/
drive
```

To view or get individual code samples, see the
google-api-nodejs-client
GitHub repository.


### Obj-C

Get the latest
Google Drive API client library for Objective-C for
REST
.

If you're building from CocoaPods, add the required pod to the
Podfile
in
your environment:


```
pod
'
GoogleAPIClientForREST
/
Drive
'
```

To view or get individual code samples, see the
google-api-objectivec-client-for-rest
GitHub repository.


### PHP

Get the latest
Google Drive API client library for
PHP
.

To use Composer, run the following command to install this client library in
your environment:


```
composer require google/apiclient:^2.15.0
```

To download and install the release instead, extract the download file
and include the autoloader in your project:


```
require_once '/path/to/google-api-php-client/vendor/autoload.php';
```

To view or get individual code samples, see the
google-api-php-client
GitHub repository.


### Python

Get the latest
Google Drive API client library for
Python
.

Install this client library in a
virtualenv
in your environment
using
pip
.

To install on Mac or Linux:


```
pip3
install
virtualenv
virtualenv
<
your
-
env
>
source
<
your
-
env
>
/
bin
/
activate
<
your
-
env
>
/
bin
/
pip
install
google
-
api
-
python
-
client
```

To install on Windows:


```
pip
install
virtualenv
virtualenv
<
your
-
env
>
<
your
-
env
>\
Scripts
\
activate
<
your
-
env
>\
Scripts
\
pip
.
exe
install
google
-
api
-
python
-
client
```

To view or get individual code samples, see the
google-api-python-client
GitHub repository.


### Ruby

Get the latest
Google Drive API client library for
Ruby
.

To use
gem install
, run the following command to install this client
library in your environment:


```
gem
install
google
-
apis
-
drive_v3
-
v
0
.
5
.
0
```

To require the file instead, add it to your
Gemfile
, add the require
statement in your project, and instantiate the service:


```
require
'google/apis/drive_v3'
drive
=
Google
::
Apis
::
DriveV3
::
DriveService
.
new
```

To view or get individual code samples, see the
google-api-ruby-client
GitHub repository.

Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2026-04-20 UTC.


---

# Configure a Drive UI integration Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/guides/enable-sdk

- Home
- Google Workspace
- Google Drive
- Guides
To display your app in Google Drive when a user creates or opens a file, you
must first set up a Drive user interface (UI) integration.
Configuration is also required to list your app in the
Google Workspace Marketplace
.


## Enable the Drive API

Before using Google APIs, you must turn them on in a Google Cloud
project. You can turn on one or more APIs in a single Google Cloud
project.

To get started integrating with the Google Drive UI, you must enable the
Drive API. This gives you access to the API and the UI integration
features.

- In the Google Cloud console, enable the Google Drive API.
Enable the API
In the Google Cloud console, enable the Google Drive API.

Enable the API


## Set up Drive UI integration

- In the Google API Console, go to Menu
menu
>
APIs & Services
>
Enabled APIs & services
.
Go to Enabled APIs & services
Go to Enabled APIs & services

- At the bottom of the APIs & Services dashboard, click
Google Drive API
. The
Google Drive API configuration page appears.
- Select the
Drive UI integration
tab.
- (Optional) Enter a name in the
Application name
field. The application
name is displayed to users in the Manage Apps tab in Drive
settings.
- (Optional) Enter a short, one-line description in the
Short description
field. The short description is displayed to users in the Manage Apps tab in
Drive settings.
- (Optional) Enter a full description in the
Long description
field.
- Upload one or more
Application icons
to display in a user's list of
connected Drive apps and in the "Open with" context menu.
Icons should be in PNG format with a transparent background. Icons can take
up to 24 hours to appear in Drive.
Upload one or more
Application icons
to display in a user's list of
connected Drive apps and in the "Open with" context menu.
Icons should be in PNG format with a transparent background. Icons can take
up to 24 hours to appear in Drive.

- To use
Drive UI's "Open with" menu
item
, enter the URL to your app in the
Open URL
field. This URL is used by the "Open With" context menu.
This URL must contain a fully qualified domain name;
localhost
doesn't
work.
This URL should be accessible to the intended users of your application.
If you have multiple application versions, such as one for public
release and one for restricted release to select users, each version
should use a unique URL. You can then create different app
configurations for each version.
You must
verify ownership of this URL
before you can list your app in the Google Workspace Marketplace.
By default, a
state
query parameter is appended to this URL to pass
data from the Drive UI to your app. For information on
the contents of the
state
parameter, see
The
state
parameter
.
To use
Drive UI's "Open with" menu
item
, enter the URL to your app in the
Open URL
field. This URL is used by the "Open With" context menu.

- This URL must contain a fully qualified domain name;
localhost
doesn't
work.
- This URL should be accessible to the intended users of your application.
If you have multiple application versions, such as one for public
release and one for restricted release to select users, each version
should use a unique URL. You can then create different app
configurations for each version.
- You must
verify ownership of this URL
before you can list your app in the Google Workspace Marketplace.
- By default, a
state
query parameter is appended to this URL to pass
data from the Drive UI to your app. For information on
the contents of the
state
parameter, see
The
state
parameter
.
- (Optional) Enter default MIME types and file extensions in the
Default MIME types
and
Default file extensions
fields. Default MIME
types and file extensions represent files your app is uniquely built to
open. For example, your app might open a built-in format for layering and
editing images. Only include standard
media
types
and make sure they're free of typos and misspellings. If your app only opens
shortcut or third-party shortcut files, you can leave MIME type blank.
(Optional) Enter default MIME types and file extensions in the
Default MIME types
and
Default file extensions
fields. Default MIME
types and file extensions represent files your app is uniquely built to
open. For example, your app might open a built-in format for layering and
editing images. Only include standard
media
types
and make sure they're free of typos and misspellings. If your app only opens
shortcut or third-party shortcut files, you can leave MIME type blank.

- (Optional) Enter secondary MIME types and file extensions in the
Secondary
MIME types
and
Secondary file extensions
fields. Secondary MIME types
and file extensions represent files your app can open, but are not specific
to your app. For example, your app might be an image-editing app that opens
PNG and JPG images. Only include standard
media
types
and make sure they're free of typos and misspellings. If your app only opens
shortcut or third-party shortcut files, you can leave MIME type blank.
(Optional) Enter secondary MIME types and file extensions in the
Secondary
MIME types
and
Secondary file extensions
fields. Secondary MIME types
and file extensions represent files your app can open, but are not specific
to your app. For example, your app might be an image-editing app that opens
PNG and JPG images. Only include standard
media
types
and make sure they're free of typos and misspellings. If your app only opens
shortcut or third-party shortcut files, you can leave MIME type blank.

- To use
Drive UI's "New"
button
and have users create a file with
your app, check the
Creating files
box. The
New URL
and optional
Document name
fields appear.
This URL must contain a fully qualified domain name;
localhost
doesn't
work.
You must
verify ownership of this
URL
before you can list your app in the Google Workspace Marketplace.
By default, a
state
query parameter is appended to this URL to pass
data from the Drive UI to your app. For information on
the contents of the
state
parameter, see
The
state
parameter
.
To use
Drive UI's "New"
button
and have users create a file with
your app, check the
Creating files
box. The
New URL
and optional
Document name
fields appear.

- You must
verify ownership of this
URL
before you can list your app in the Google Workspace Marketplace.
- Enter a URL in the
New URL
field. This URL is used by the "New" button
to redirect the user to your application.
Enter a URL in the
New URL
field. This URL is used by the "New" button
to redirect the user to your application.

- (Optional) If you want your app to open Google Workspace-supported files,
check the
Importing
box.
(Optional) If you want your app to open Google Workspace-supported files,
check the
Importing
box.

- (Optional) If your app must manage files on shared drives, check the
Shared drives support
box. For further information on how to support
shared drives in your app, see
Implement shared drive
support
.
(Optional) If your app must manage files on shared drives, check the
Shared drives support
box. For further information on how to support
shared drives in your app, see
Implement shared drive
support
.

- Click
Submit
.
Click
Submit
.


## Request the
drive.install
scope

To allow apps to appear as an option in the "Open with" or the "New" menu,
request the
https://www.googleapis.com/auth/drive.install
scope to integrate
with the Drive UI. When requesting this scope, users receive a
dialog similar to this:

For more information about scopes you can request for Drive apps,
and how to request them, see
API-specific authorization and authentication
information
.


### The
state
parameter

By default, a
state
parameter is appended to both the Open URL and the New URL
to pass data from the Drive UI to your app. This parameter
contains a JSON-encoded string with template variables and data about the
request to your app. The variables included depend on the type of URL used (Open
URL or New URL):


| Template variable | Description | URL application |
| --- | --- | --- |
| {ids} | A comma-separated list of file IDs being opened. | Open URL |
| {exportIds} | A comma-separated list of file IDs being exported. Used only when opening Google Workspace files. | Open URL |
| {resourceKeys} | A JSON dictionary of file IDs mapped to their respective resource
 keys. | Open URL |
| {folderId} | The ID of the parent folder. | New URL |
| {folderResourceKey} | The resource key of the parent folder. | New URL |
| {userId} | The profile ID that identifies the user. | Open URL and New URL |
| {action} | The action being performed. The value is
open
when using an Open URL or
create
when using a New URL. | Open URL and New URL |

The
state
parameter is URL-encoded, so your app must handle the escape
characters and parse it as JSON. Apps can detect the
create
value in the
state
parameter to verify a request to create a file.


#### Example state information in JSON for a New URL

The
state
information for a New URL is:


```
{
  "action":"create",
  "folderId":"
FOLDER_ID
",
  "folderResourceKey":"
FOLDER_RESOURCE_KEY
",
  "userId":"
USER_ID
"
}
```


#### Example state information in JSON for an Open URL

The
state
information for an Open URL is:


```
{
  "ids": ["
ID
"],
  "resourceKeys":{"
RESOURCE_KEYS
":"
RESOURCE_KEYS
"},
  "action":"open",
  "userId":"
USER_ID
"
}
```

The IDs and resource keys are used to fetch file metadata and download file
content. Once your app has the file ID and an access token, it can check
permissions, fetch the file metadata, and download the file content as described
in the
files.get
method.


## Related topics

An installed app must be able to create, manage, and open actions launched from
the Drive UI. To learn more, see
Integrate with
Drive UI's "New" button
or
Integrate with Drive UI's "Open with" context
menu
.

Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2026-04-23 UTC.


---

# Implement shared drive support Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/guides/enable-shareddrives

- Home
- Google Workspace
- Google Drive
- Guides
Shared drives follow different organization, sharing, and ownership models from
My Drive. If your app is going to create and manage files on
shared drives, you must implement shared drive support in your app. The
complexity of your implementation depends on the functionality of your app.

To begin, you must include the
supportsAllDrives=true
query parameter in your
requests when your app performs the following operations:


### Drive API v3

- files.get
- files.list
- files.create
- files.update
- files.copy
- files.delete
- changes.list
- changes.getStartPageToken
- permissions.list
- permissions.get
- permissions.create
- permissions.update
- permissions.delete

### Drive API v2

- files.insert
- files.patch
- files.trash
- files.untrash
- files.touch
- children.insert
- parents.insert
- changes.get
- permissions.insert
- permissions.patch
The
supportsAllDrives=true
parameter informs Google Drive that your
application is designed to handle files on shared drives.

Applications that read or modify permissions, track changes, or search across
multiple corpora require additional shared drive capabilities. The remainder of
this document highlights additional changes required to perform these tasks.


## Search for content on a shared drive

Use the
list
method on the
files
resource to find user files in shared drives. To
search for a shared drive, see
Search for shared
drives
.

The
list
method contains the following shared drive-specific query parameters:

- driveId
: ID of the shared drive to search.
driveId
: ID of the shared drive to search.

- corpora
: Bodies of items (files or documents) to which the query applies.
Supported bodies are
user
,
domain
,
drive
, and
allDrives
. Prefer
user
or
drive
to
allDrives
for efficiency. By default, corpora is set
to
user
.
corpora
: Bodies of items (files or documents) to which the query applies.
Supported bodies are
user
,
domain
,
drive
, and
allDrives
. Prefer
user
or
drive
to
allDrives
for efficiency. By default, corpora is set
to
user
.

- includeItemsFromAllDrives
: Whether both My Drive and shared
drive items should be included in results. If not present or set to false,
then shared drive items are not returned.
includeItemsFromAllDrives
: Whether both My Drive and shared
drive items should be included in results. If not present or set to false,
then shared drive items are not returned.

- supportsAllDrives
: Whether the requesting application supports both My
Drive and shared drive. If false, shared drive items are not
included in the response.
supportsAllDrives
: Whether the requesting application supports both My
Drive and shared drive. If false, shared drive items are not
included in the response.

The following query modes are specific to shared drives:


| includeItemsFromAllDrives | corpora | Query description |
| --- | --- | --- |
| true | user | Queries files that the user has accessed, including both shared drive and My Drive files. |
| true | domain | Queries files that are shared to the domain, including both shared drive and My Drive files. |
| true | drive | Queries all items in the specified shared drive. The
driveId
must be specified in the request. |
| true | allDrives | Queries files that the user has accessed and all shared drives in which they're a member. Note that the response might include
incompleteSearch:true
, indicating that some corpora were not searched for this request. |


## Track changes on a shared drive

Use the
list
method on the
changes
resource to track changes on a shared drive. For
more information, see
Track changes for users and shared
drives
.

- driveId
: The shared drive from which changes are returned. If specified,
the change IDs refer to changes to items within the shared drive providing
the current state of a file. To refer to a specific shared drive change,
both the shared drive ID and change ID must be used as an identifier.
driveId
: The shared drive from which changes are returned. If specified,
the change IDs refer to changes to items within the shared drive providing
the current state of a file. To refer to a specific shared drive change,
both the shared drive ID and change ID must be used as an identifier.

- includeItemsFromAllDrives
: Whether shared drive files or changes should be
included in the list of changes.
includeItemsFromAllDrives
: Whether shared drive files or changes should be
included in the list of changes.

- supportsAllDrives
: Whether the requesting application supports shared
drives. If false, then shared drive items, including both shared drives and
files within a shared drive, aren't returned.
supportsAllDrives
: Whether the requesting application supports shared
drives. If false, then shared drive items, including both shared drives and
files within a shared drive, aren't returned.


| includeItemsFromAllDrives | driveId | Query description |
| --- | --- | --- |
| true | No | Changes are reflective of changes to files inside or outside of shared drives that the user has accessed, as well as changes to shared drives in which the user is a member. |
| true | Yes | Changes are reflective of changes to the particular shared drive that was specified and items inside that shared drive. |

For additional details about change log behavior, see
Track changes for users
and shared drives
.


## Enable shared drive support in the Drive UI

To access shared drive content using the Drive UI, make sure you
have checked the
Shared drives support
box on the
Drive UI integration
tab
of the Google Drive API in the
Google Cloud console
. For more
information, see
Configure a Drive UI integration
.


## Use the Google Picker with shared drives

The
Google Picker
supports selecting items in shared
drives. For details about enabling shared drive support and adding shared drives
views in the picker, see the
Google Picker API
.


## Related topics

- Manage shared drives
Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2026-04-20 UTC.


---

# Return specific fields Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/guides/fields-parameter

- Home
- Google Workspace
- Google Drive
- Guides
This document explains how to use the
fields
parameter in Google Drive.

To return the exact fields you need, and to improve performance, use the
fields
system
parameter
in
your method call.

For information on other system parameters that apply to Drive API,
see
Alternative system parameters
.


## How the fields parameter works

The
fields
parameter uses a
FieldMask
for response filtering. Field masks are used to specify a subset of fields that
a request should return. Using a field mask is good design practice to make sure
that you don't request unnecessary data, which in turn helps avoid unnecessary
processing time.

If you don't specify the
fields
parameter, the server returns a default set of
fields specific to the method. For example, the
list
method on the
files
method only returns the
kind
,
id
,
name
, and
mimeType
fields. The
get
method on the
permissions
resource returns a different set
of default fields.

For all methods of the
about
,
comments
(excluding
delete
), and
replies
(excluding
delete
) resources you
must
set the
fields
parameter. These methods don't return a default set of fields.

After a server processes a valid request that includes the
fields
parameter,
it returns an
HTTP 200 OK
status code, along with the requested data. If the
fields parameter has an error or is otherwise invalid, the server returns an
HTTP 400 Bad Request
status code, along with an error message stating what's
wrong with your fields selection. For example,
files.list(fields='files(id,capabilities,canAddChildren)')
yields an error of
"Invalid field selection canAddChildren." The correct fields parameter for this
example is
files.list(fields='files(id,capabilities/canAddChildren)')
.

To determine the fields you can return using the
fields
parameter, visit the
documentation page of the resource you're querying. For example, to see what
fields you can return for a file, refer to the
files
resource documentation.
For more file-specific query terms, see
Search query terms and operators
.


## Field parameter format rules

The format of the fields request parameter value is loosely based on XPath
syntax. The following are formatting rules for the
fields
parameter. All these
rules use examples related to the
files.get
method.

- Use a comma-separated list to select multiple fields, such as
'name,
mimeType'
.
Use a comma-separated list to select multiple fields, such as
'name,
mimeType'
.

- Use
a/b
to select field
b
that's nested within field
a
, such as
'capabilities/canDownload'
. For more information, see
Fetch the fields of
a nested resource
.
Use
a/b
to select field
b
that's nested within field
a
, such as
'capabilities/canDownload'
. For more information, see
Fetch the fields of
a nested resource
.

- Use a sub-selector to request a set of specific sub-fields of arrays or
objects by placing expressions in parentheses "()". For example,
'permissions(id)'
returns only the permission ID for each element in the
permissions array.
Use a sub-selector to request a set of specific sub-fields of arrays or
objects by placing expressions in parentheses "()". For example,
'permissions(id)'
returns only the permission ID for each element in the
permissions array.

- To return all fields in an object, use an asterisk (
*
) as a wildcard in
field selections. For example,
'permissions/permissionDetails/*'
selects
all available permission details fields per permission. Note that using the
wildcard can lead to negative performance impacts on the request.
To return all fields in an object, use an asterisk (
*
) as a wildcard in
field selections. For example,
'permissions/permissionDetails/*'
selects
all available permission details fields per permission. Note that using the
wildcard can lead to negative performance impacts on the request.

Request

In this example, we provide the file ID path parameter and multiple fields as a query parameter in the request. The response returns the field values for the file ID.


```bash
GET https://www.googleapis.com/drive/v3/files/
FILE_ID
?fields=name,starred,shared
```

Response


```
{
  "name": "File1",
  "starred": false,
  "shared": true
  }
}
```


## Fetch the fields of a nested resource

When a field refers to another resource, you can specify which fields of the
nested resource should be fetched.

For example, to retrieve the
role
field (nested resource) of the
permissions
resource, use any of the following options:

- permissions.get
with
fields=role
.
- permissions.get
with
fields=*
to show all
permissions
fields.
- files.get
with
fields=permissions(role)
or
fields=permissions/role
.
- files.get
with
fields=permissions
to show all
permissions
fields.
- changes.list
with
fields=changes(file(permissions(role)))
.
To retrieve multiple fields, use a comma-separated list. For example,
files.list
with
fields=files(id,name,createdTime,modifiedTime,size)
.

In this example, we provide the file ID path parameter and multiple fields, including certain fields of the nested permissions resource, as a query parameter in the request. The response returns the field values for the file ID.


```
GET
https
:
//www.googleapis.com/drive/v3/files/
FILE_ID
?fields=name,starred,shared,permissions(kind,type,role)
```


```
{
"name"
:
"File1"
,
"starred"
:
false
,
"shared"
:
true
,
"permissions"
:
[
{
"kind"
:
"drive#permission"
,
"type"
:
"user"
,
"role"
:
"owner"
}
]
}
```


## Alternative system parameters

Query parameters that apply to all Google Drive API operations are documented at
System Parameters
.


## Related topics

- Resolve errors
- Troubleshoot authentication and authorization issues
- Improve performance
Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2026-04-20 UTC.


---

# Manage file metadata Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/guides/file

- Home
- Google Workspace
- Google Drive
- Guides
This document covers important considerations for naming files and working with
metadata like indexable text and thumbnails. To insert and retrieve files, see
the
files
resource.


## Metadata overview

In the Google Drive API, the
files
resource represents the metadata. Unlike APIs
where metadata is a sub-object, the Drive API treats the entire
files
resource as metadata. You can access the metadata directly through the
get
or
list
methods on the
files
resource.

By default, the
get
and
list
methods return only a partial set of fields. To
retrieve specific data, you must define the
fields
system
parameter
in
your request. If omitted, the server returns a default subset of fields specific
to the method. For example, the
list
method returns only the
kind
,
id
,
name
,
mimeType
, and
resourceKey
fields for each file. To return different
fields, see
Return specific fields
.

Additionally, metadata visibility depends on the user's role on the file. The
permissions
resource doesn't determine a
user's allowed actions on a file or folder. Instead, the
files
resource
contains a collection of boolean
capabilities
fields. The
Google Drive API derives these
capabilities
from the
permissions
resource
associated with the file or folder. For more information, see
Understand file
capabilities
.

The Drive API offers two restricted metadata scopes:
drive.metadata
and
drive.metadata.readonly
. The
drive.metadata
scope lets you view and
manage file metadata, while
drive.metadata.readonly
is read-only. Both
strictly prohibit access to file content. For more information, see
Choose
Google Drive API scopes
.

Finally, always verify your logic regarding permissions and scopes. For example,
a user might own a file with full permissions, but the Drive API will
block attempts to modify or download the file if your app only has the
drive.metadata.readonly
scope.


## Specify file names and extensions

Apps should specify a file extension in the
name
) property when inserting
files with the Google Drive API. For example, an operation to insert a JPEG file
should specify something like
"name": "cat.jpg"
in the metadata.

Subsequent
GET
responses can include the read-only
fileExtension
property populated with the
extension originally specified in the
name
property. When a Google Drive
user requests to download a file, or when the file is downloaded through the
sync client, Drive builds a full filename (with extension) based
on the name. In cases where the extension is missing, Drive
attempts to determine the extension based on the file's MIME type.


## Save indexable text

Drive automatically indexes documents for search when it
recognizes the file type, including text documents, PDFs, images with text, and
other common types. If your app saves other types of files (such as drawings,
video, and shortcuts), you can improve the discoverability by supplying
indexable text in the
contentHints.indexableText
field of the file.

Indexable text is indexed as HTML. If you save the indexable text string
<section attribute="value1">Here's some text</section>
, then "Here's some
text" is indexed, but "value1" isn't. Because of this, saving XML as indexable
text isn't as useful as saving HTML.

When specifying
indexableText
, also keep in mind:

- The size limit for
contentHints.indexableText
is 128 KB.
- Capture the key terms and concepts that you expect a user to search.
- Don't try to sort text in order of importance because the indexer does that
efficiently for you.
- Your application should update the indexable text with each save.
- Make sure the text is related to the file's content or metadata.
This last point might seem obvious, but it's important. It's not a good idea to
add commonly searched terms to force a file to appear in search results. This
can frustrate users, and might even motivate them to delete the file.


## Upload thumbnails

Drive automatically generates thumbnails for many common file
types, such as Google Docs, Sheets, and Slides.
Thumbnails help the user to better identify Drive files.

For file types that Drive can't generate a standard thumbnail
for, you can provide a thumbnail image generated by your application. During
file creation or update, upload a thumbnail by setting the
contentHints.thumbnail
field on the
files
resource.

Specifically:

- Set the
contentHints.thumbnail.image
field to the URL and filename safe
base64-encoded image (see
RFC 4648 section
5
).
- Set the
contentHints.thumbnail.mimeType
field to the appropriate MIME type
for the thumbnail.
If Drive can generate a thumbnail from the file, it uses the
automatically generated one and ignores any you might have uploaded. If it can't
generate a thumbnail, it uses the one you provide.

Thumbnails should adhere to these rules:

- Can be uploaded in PNG, GIF, or JPG formats.
- The recommended width is 1600 pixels.
- The minimum width is 220 pixels.
- The maximum file size is 2 MB.
- They should be updated by your application with each save.
For more information, see the
files
resource.


## Retrieve thumbnails

You can retrieve metadata, including thumbnails, for Drive files.
Thumbnail information is housed in the
thumbnailLink
field of
the
files
resource.


### Return a specific thumbnail

The following code sample shows a
get
method
request with multiple fields as a query parameter to return the
thumbnailLink
metadata for a specific file. For more information, see
Return specific fields
for a file
.


```bash
GET https://www.googleapis.com/drive/v3/files/
FILE_ID
?fields=id,name,mimeType,thumbnailLink
```

Replace
FILE_ID
with the
fileId
of the file that you want to
find.

If available, the request returns a short-lived URL to the file's thumbnail.
Typically, the link lasts for several hours. The field is only populated when
the requesting app can access the file's content. If the file isn't shared
publicly, the URL returned in
thumbnailLink
must be fetched using a
credentialed request
.


### Return a list of thumbnails

The following code sample shows a
list
method
request with multiple fields as a query parameter to return the
thumbnailLink
metadata for a list of files. For more information, see
Search for files and
folders
.


```bash
GET https://www.googleapis.com/drive/v3/files/?fields=files(id,name,mimeType,thumbnailLink)
```

To restrict the search results to a specific file type, apply a query string to
set the MIME type. For example, the following code sample shows how to limit the
list to Google Sheets files. For more information on MIME types, see
Google Workspace and Google Drive supported MIME
types
.


```bash
GET https://www.googleapis.com/drive/v3/files/q=mimeType='application/vnd.google-apps.spreadsheet'&fields=files(id,name,mimeType,thumbnailLink)
```


## Related topics

- Store application-specific data
- Add custom file properties
Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2026-04-20 UTC.


---

# Create and populate folders Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/guides/folder

- Home
- Google Workspace
- Google Drive
- Guides
Folders
are files that only contain metadata and can be used to organize files
in Google Drive. They have the following properties:

- A folder is a file with the
MIME type
application/vnd.google-apps.folder
and it has no extension.
- The alias
root
can be used to refer to the root folder anywhere a file ID
is provided.
For more information about Drive folder limits, see
File and
folder limits
.

This guide explains how to perform some basic folder-related tasks.


## Create a folder

To create a folder, use the
files.create()
method with the
mimeType
of
application/vnd.google-apps.folder
and a
name
.
The following code sample shows how to create a folder using a client library:


### Java


```
import
com.google.api.client.googleapis.json.GoogleJsonResponseException
;
import
com.google.api.client.http.HttpRequestInitializer
;
import
com.google.api.client.http.javanet.NetHttpTransport
;
import
com.google.api.client.json.gson.GsonFactory
;
import
com.google.api.services.drive.Drive
;
import
com.google.api.services.drive.DriveScopes
;
import
com.google.api.services.drive.model.File
;
import
com.google.auth.http.HttpCredentialsAdapter
;
import
com.google.auth.oauth2.GoogleCredentials
;
import
java.io.IOException
;
import
java.util.Arrays
;
/* Class to demonstrate use of Drive's create folder API */
public
class
CreateFolder
{
/**
* Create new folder.
*
* @return Inserted folder id if successful, {@code null} otherwise.
* @throws IOException if service account credentials file not found.
*/
public
static
String
createFolder
()
throws
IOException
{
// Load pre-authorized user credentials from the environment.
// TODO(developer) - See https://developers.google.com/identity for
// guides on implementing OAuth2 for your application.
GoogleCredentials
credentials
=
GoogleCredentials
.
getApplicationDefault
()
.
createScoped
(
Arrays
.
asList
(
DriveScopes
.
DRIVE_FILE
));
HttpRequestInitializer
requestInitializer
=
new
HttpCredentialsAdapter
(
credentials
);
// Build a new authorized API client service.
Drive
service
=
new
Drive
.
Builder
(
new
NetHttpTransport
(),
GsonFactory
.
getDefaultInstance
(),
requestInitializer
)
.
setApplicationName
(
"Drive samples"
)
.
build
();
// File's metadata.
File
fileMetadata
=
new
File
();
fileMetadata
.
setName
(
"Test"
);
fileMetadata
.
setMimeType
(
"application/vnd.google-apps.folder"
);
try
{
File
file
=
service
.
files
().
create
(
fileMetadata
)
.
setFields
(
"id"
)
.
execute
();
System
.
out
.
println
(
"Folder ID: "
+
file
.
getId
());
return
file
.
getId
();
}
catch
(
GoogleJsonResponseException
e
)
{
// TODO(developer) - handle error appropriately
System
.
err
.
println
(
"Unable to create folder: "
+
e
.
getDetails
());
throw
e
;
}
}
}
```


### Python


```
import
google.auth
from
googleapiclient.discovery
import
build
from
googleapiclient.errors
import
HttpError
def
create_folder
():
"""Create a folder and prints the folder ID
Returns : Folder Id
Load pre-authorized user credentials from the environment.
TODO(developer) - See https://developers.google.com/identity
for guides on implementing OAuth2 for the application.
"""
creds
,
_
=
google
.
auth
.
default
()
try
:
# create drive api client
service
=
build
(
"drive"
,
"v3"
,
credentials
=
creds
)
file_metadata
=
{
"name"
:
"Invoices"
,
"mimeType"
:
"application/vnd.google-apps.folder"
,
}
# pylint: disable=maybe-no-member
file
=
service
.
files
()
.
create
(
body
=
file_metadata
,
fields
=
"id"
)
.
execute
()
print
(
f
'Folder ID: "
{
file
.
get
(
"id"
)
}
".'
)
return
file
.
get
(
"id"
)
except
HttpError
as
error
:
print
(
f
"An error occurred:
{
error
}
"
)
return
None
if
__name__
==
"__main__"
:
create_folder
()
```


### Node.js


```
import
{
GoogleAuth
}
from
'google-auth-library'
;
import
{
google
}
from
'googleapis'
;
/**
* Creates a new folder in Google Drive.
* @return {Promise<string|null|undefined>} The ID of the created folder.
*/
async
function
createFolder
()
{
// Authenticate with Google and get an authorized client.
// TODO (developer): Use an appropriate auth mechanism for your app.
const
auth
=
new
GoogleAuth
({
scopes
:
'https://www.googleapis.com/auth/drive'
,
});
// Create a new Drive API client (v3).
const
service
=
google
.
drive
({
version
:
'v3'
,
auth
});
// The metadata for the new folder.
const
fileMetadata
=
{
name
:
'Invoices'
,
mimeType
:
'application/vnd.google-apps.folder'
,
};
// Create the new folder.
const
file
=
await
service
.
files
.
create
({
requestBody
:
fileMetadata
,
fields
:
'id'
,
});
// Print the ID of the new folder.
console
.
log
(
'Folder Id:'
,
file
.
data
.
id
);
return
file
.
data
.
id
;
}
```


### PHP


```
<
?php
use Google\Client;
use Google\Service\Drive;
function createFolder()
{
try {
$client = new Client();
$client->useApplicationDefaultCredentials();
$client->addScope(Drive::DRIVE);
$driveService = new Drive($client);
$fileMetadata = new Drive\DriveFile(array(
'name' => 'Invoices',
'mimeType' => 'application/vnd.google-apps.folder'));
$file = $driveService->files->create($fileMetadata, array(
'fields' => 'id'));
printf("Folder ID: %s\n", $file->id);
return $file->id;
}catch(Exception $e) {
echo "Error Message: ".$e;
}
}
```


### .NET


```
using
Google.Apis.Auth.OAuth2
;
using
Google.Apis.Drive.v3
;
using
Google.Apis.Services
;
namespace
DriveV3Snippets
{
// Class to demonstrate use of Drive create folder API.
public
class
CreateFolder
{
/// <summary>
/// Creates a new folder.
/// </summary>
/// <returns>created folder id, null otherwise</returns>
public
static
string
DriveCreateFolder
()
{
try
{
/* Load pre-authorized user credentials from the environment.
TODO(developer) - See https://developers.google.com/identity for
guides on implementing OAuth2 for your application. */
GoogleCredential
credential
=
GoogleCredential
.
GetApplicationDefault
()
.
CreateScoped
(
DriveService
.
Scope
.
Drive
);
// Create Drive API service.
var
service
=
new
DriveService
(
new
BaseClientService
.
Initializer
{
HttpClientInitializer
=
credential
,
ApplicationName
=
"Drive API Snippets"
});
// File metadata
var
fileMetadata
=
new
Google
.
Apis
.
Drive
.
v3
.
Data
.
File
()
{
Name
=
"Invoices"
,
MimeType
=
"application/vnd.google-apps.folder"
};
// Create a new folder on drive.
var
request
=
service
.
Files
.
Create
(
fileMetadata
);
request
.
Fields
=
"id"
;
var
file
=
request
.
Execute
();
// Prints the created folder id.
Console
.
WriteLine
(
"Folder ID: "
+
file
.
Id
);
return
file
.
Id
;
}
catch
(
Exception
e
)
{
// TODO(developer) - handle error appropriately
if
(
e
is
AggregateException
)
{
Console
.
WriteLine
(
"Credential Not found"
);
}
else
{
throw
;
}
}
return
null
;
}
}
}
```


## Create a file in a specific folder

To create a file in a specific folder, use the
files.create()
method and specify the folder ID in the
parents
property of the file.

The
parents
property holds the ID of the parent folder containing the file.
The
parents
property can be used when creating files in a top-level folder or
any other folder.

A file can only have one parent folder. Specifying multiple parents isn't
supported. If the
parents
field isn't specified, the file is placed directly
in the user's My Drive folder.

The following code sample shows how to create a file in a specific folder using
a client library:


```
import
com.google.api.client.googleapis.json.GoogleJsonResponseException
;
import
com.google.api.client.http.FileContent
;
import
com.google.api.client.http.HttpRequestInitializer
;
import
com.google.api.client.http.javanet.NetHttpTransport
;
import
com.google.api.client.json.gson.GsonFactory
;
import
com.google.api.services.drive.Drive
;
import
com.google.api.services.drive.DriveScopes
;
import
com.google.api.services.drive.model.File
;
import
com.google.auth.http.HttpCredentialsAdapter
;
import
com.google.auth.oauth2.GoogleCredentials
;
import
java.io.IOException
;
import
java.util.Arrays
;
import
java.util.Collections
;
/* Class to demonstrate Drive's upload to folder use-case. */
public
class
UploadToFolder
{
/**
* Upload a file to the specified folder.
*
* @param realFolderId Id of the folder.
* @return Inserted file metadata if successful, {@code null} otherwise.
* @throws IOException if service account credentials file not found.
*/
public
static
File
uploadToFolder
(
String
realFolderId
)
throws
IOException
{
// Load pre-authorized user credentials from the environment.
// TODO(developer) - See https://developers.google.com/identity for
// guides on implementing OAuth2 for your application.
GoogleCredentials
credentials
=
GoogleCredentials
.
getApplicationDefault
()
.
createScoped
(
Arrays
.
asList
(
DriveScopes
.
DRIVE_FILE
));
HttpRequestInitializer
requestInitializer
=
new
HttpCredentialsAdapter
(
credentials
);
// Build a new authorized API client service.
Drive
service
=
new
Drive
.
Builder
(
new
NetHttpTransport
(),
GsonFactory
.
getDefaultInstance
(),
requestInitializer
)
.
setApplicationName
(
"Drive samples"
)
.
build
();
// File's metadata.
File
fileMetadata
=
new
File
();
fileMetadata
.
setName
(
"photo.jpg"
);
fileMetadata
.
setParents
(
Collections
.
singletonList
(
realFolderId
));
java
.
io
.
File
filePath
=
new
java
.
io
.
File
(
"files/photo.jpg"
);
FileContent
mediaContent
=
new
FileContent
(
"image/jpeg"
,
filePath
);
try
{
File
file
=
service
.
files
().
create
(
fileMetadata
,
mediaContent
)
.
setFields
(
"id, parents"
)
.
execute
();
System
.
out
.
println
(
"File ID: "
+
file
.
getId
());
return
file
;
}
catch
(
GoogleJsonResponseException
e
)
{
// TODO(developer) - handle error appropriately
System
.
err
.
println
(
"Unable to upload file: "
+
e
.
getDetails
());
throw
e
;
}
}
}
```


```
import
google.auth
from
googleapiclient.discovery
import
build
from
googleapiclient.errors
import
HttpError
from
googleapiclient.http
import
MediaFileUpload
def
upload_to_folder
(
folder_id
):
"""Upload a file to the specified folder and prints file ID, folder ID
Args: Id of the folder
Returns: ID of the file uploaded
Load pre-authorized user credentials from the environment.
TODO(developer) - See https://developers.google.com/identity
for guides on implementing OAuth2 for the application.
"""
creds
,
_
=
google
.
auth
.
default
()
try
:
# create drive api client
service
=
build
(
"drive"
,
"v3"
,
credentials
=
creds
)
file_metadata
=
{
"name"
:
"photo.jpg"
,
"parents"
:
[
folder_id
]}
media
=
MediaFileUpload
(
"download.jpeg"
,
mimetype
=
"image/jpeg"
,
resumable
=
True
)
# pylint: disable=maybe-no-member
file
=
(
service
.
files
()
.
create
(
body
=
file_metadata
,
media_body
=
media
,
fields
=
"id"
)
.
execute
()
)
print
(
f
'File ID: "
{
file
.
get
(
"id"
)
}
".'
)
return
file
.
get
(
"id"
)
except
HttpError
as
error
:
print
(
f
"An error occurred:
{
error
}
"
)
return
None
if
__name__
==
"__main__"
:
upload_to_folder
(
folder_id
=
"1s0oKEZZXjImNngxHGnY0xed6Mw-tvspu"
)
```


```
import
fs
from
'node:fs'
;
import
{
GoogleAuth
}
from
'google-auth-library'
;
import
{
google
}
from
'googleapis'
;
/**
* Uploads a file to the specified folder.
* @param {string} folderId The ID of the folder to upload the file to.
* @return {Promise<string>} The ID of the uploaded file.
*/
async
function
uploadToFolder
(
folderId
)
{
// Authenticate with Google and get an authorized client.
// TODO (developer): Use an appropriate auth mechanism for your app.
const
auth
=
new
GoogleAuth
({
scopes
:
'https://www.googleapis.com/auth/drive'
,
});
// Create a new Drive API client (v3).
const
service
=
google
.
drive
({
version
:
'v3'
,
auth
});
// The request body for the file to be uploaded.
const
requestBody
=
{
name
:
'photo.jpg'
,
parents
:
[
folderId
],
};
// The media content to be uploaded.
const
media
=
{
mimeType
:
'image/jpeg'
,
body
:
fs
.
createReadStream
(
'files/photo.jpg'
),
};
// Upload the file to the specified folder.
const
file
=
await
service
.
files
.
create
({
requestBody
,
media
,
fields
:
'id'
,
});
// Print the ID of the uploaded file.
console
.
log
(
'File Id:'
,
file
.
data
.
id
);
if
(
!
file
.
data
.
id
)
{
throw
new
Error
(
'File ID not found.'
);
}
return
file
.
data
.
id
;
}
```


```
<
?php
use Google\Client;
use Google\Service\Drive;
function uploadToFolder($folderId)
{
try {
$client = new Client();
$client->useApplicationDefaultCredentials();
$client->addScope(Drive::DRIVE);
$driveService = new Drive($client);
$fileMetadata = new Drive\DriveFile(array(
'name' => 'photo.jpg',
'parents' => array($folderId)
));
$content = file_get_contents('../files/photo.jpg');
$file = $driveService->files->create($fileMetadata, array(
'data' => $content,
'mimeType' => 'image/jpeg',
'uploadType' => 'multipart',
'fields' => 'id'));
printf("File ID: %s\n", $file->id);
return $file->id;
} catch (Exception $e) {
echo "Error Message: " . $e;
}
}
require_once 'vendor/autoload.php';
uploadToFolder();
```


```
using
Google.Apis.Auth.OAuth2
;
using
Google.Apis.Drive.v3
;
using
Google.Apis.Services
;
namespace
DriveV3Snippets
{
// Class to demonstrate use of Drive upload to folder.
public
class
UploadToFolder
{
/// <summary>
/// Upload a file to the specified folder.
/// </summary>
/// <param name="filePath">Image path to upload.</param>
/// <param name="folderId">Id of the folder.</param>
/// <returns>Inserted file metadata if successful, null otherwise</returns>
public
static
Google
.
Apis
.
Drive
.
v3
.
Data
.
File
DriveUploadToFolder
(
string
filePath
,
string
folderId
)
{
try
{
/* Load pre-authorized user credentials from the environment.
TODO(developer) - See https://developers.google.com/identity for
guides on implementing OAuth2 for your application. */
GoogleCredential
credential
=
GoogleCredential
.
GetApplicationDefault
()
.
CreateScoped
(
DriveService
.
Scope
.
Drive
);
// Create Drive API service.
var
service
=
new
DriveService
(
new
BaseClientService
.
Initializer
{
HttpClientInitializer
=
credential
,
ApplicationName
=
"Drive API Snippets"
});
// Upload file photo.jpg in specified folder on drive.
var
fileMetadata
=
new
Google
.
Apis
.
Drive
.
v3
.
Data
.
File
()
{
Name
=
"photo.jpg"
,
Parents
=
new
List<string>
{
folderId
}
};
FilesResource
.
CreateMediaUpload
request
;
// Create a new file on drive.
using
(
var
stream
=
new
FileStream
(
filePath
,
FileMode
.
Open
))
{
// Create a new file, with metadata and stream.
request
=
service
.
Files
.
Create
(
fileMetadata
,
stream
,
"image/jpeg"
);
request
.
Fields
=
"id"
;
request
.
Upload
();
}
var
file
=
request
.
ResponseBody
;
// Prints the uploaded file id.
Console
.
WriteLine
(
"File ID: "
+
file
.
Id
);
return
file
;
}
catch
(
Exception
e
)
{
// TODO(developer) - handle error appropriately
if
(
e
is
AggregateException
)
{
Console
.
WriteLine
(
"Credential Not found"
);
}
else
if
(
e
is
FileNotFoundException
)
{
Console
.
WriteLine
(
"File not found"
);
}
else
if
(
e
is
DirectoryNotFoundException
)
{
Console
.
WriteLine
(
"Directory Not found"
);
}
else
{
throw
;
}
}
return
null
;
}
}
}
```


## Move files between folders

To move files, you must update the ID of the
parents
property.

To add or remove parents for an existing file, use the
files.update()
method with either the
addParents
and
removeParents
query parameters.

A file can only have one parent folder. Specifying multiple parents isn't
supported.

The following code sample shows how to move a file between folders using a
client library:


```
import
com.google.api.client.googleapis.json.GoogleJsonResponseException
;
import
com.google.api.client.http.HttpRequestInitializer
;
import
com.google.api.client.http.javanet.NetHttpTransport
;
import
com.google.api.client.json.gson.GsonFactory
;
import
com.google.api.services.drive.Drive
;
import
com.google.api.services.drive.DriveScopes
;
import
com.google.api.services.drive.model.File
;
import
com.google.auth.http.HttpCredentialsAdapter
;
import
com.google.auth.oauth2.GoogleCredentials
;
import
java.io.IOException
;
import
java.util.Arrays
;
import
java.util.List
;
/* Class to demonstrate use case for moving file to folder.*/
public
class
MoveFileToFolder
{
/**
* @param fileId   Id of file to be moved.
* @param folderId Id of folder where the fill will be moved.
* @return list of parent ids for the file.
*/
public
static
List<String>
moveFileToFolder
(
String
fileId
,
String
folderId
)
throws
IOException
{
/* Load pre-authorized user credentials from the environment.
TODO(developer) - See https://developers.google.com/identity for
guides on implementing OAuth2 for your application.*/
GoogleCredentials
credentials
=
GoogleCredentials
.
getApplicationDefault
()
.
createScoped
(
Arrays
.
asList
(
DriveScopes
.
DRIVE_FILE
));
HttpRequestInitializer
requestInitializer
=
new
HttpCredentialsAdapter
(
credentials
);
// Build a new authorized API client service.
Drive
service
=
new
Drive
.
Builder
(
new
NetHttpTransport
(),
GsonFactory
.
getDefaultInstance
(),
requestInitializer
)
.
setApplicationName
(
"Drive samples"
)
.
build
();
// Retrieve the existing parents to remove
File
file
=
service
.
files
().
get
(
fileId
)
.
setFields
(
"parents"
)
.
execute
();
StringBuilder
previousParents
=
new
StringBuilder
();
for
(
String
parent
:
file
.
getParents
())
{
previousParents
.
append
(
parent
);
previousParents
.
append
(
','
);
}
try
{
// Move the file to the new folder
file
=
service
.
files
().
update
(
fileId
,
null
)
.
setAddParents
(
folderId
)
.
setRemoveParents
(
previousParents
.
toString
())
.
setFields
(
"id, parents"
)
.
execute
();
return
file
.
getParents
();
}
catch
(
GoogleJsonResponseException
e
)
{
// TODO(developer) - handle error appropriately
System
.
err
.
println
(
"Unable to move file: "
+
e
.
getDetails
());
throw
e
;
}
}
}
```


```
import
google.auth
from
googleapiclient.discovery
import
build
from
googleapiclient.errors
import
HttpError
def
move_file_to_folder
(
file_id
,
folder_id
):
"""Move specified file to the specified folder.
Args:
file_id: Id of the file to move.
folder_id: Id of the folder
Print: An object containing the new parent folder and other meta data
Returns : Parent Ids for the file
Load pre-authorized user credentials from the environment.
TODO(developer) - See https://developers.google.com/identity
for guides on implementing OAuth2 for the application.
"""
creds
,
_
=
google
.
auth
.
default
()
try
:
# call drive api client
service
=
build
(
"drive"
,
"v3"
,
credentials
=
creds
)
# pylint: disable=maybe-no-member
# Retrieve the existing parents to remove
file
=
service
.
files
()
.
get
(
fileId
=
file_id
,
fields
=
"parents"
)
.
execute
()
previous_parents
=
","
.
join
(
file
.
get
(
"parents"
))
# Move the file to the new folder
file
=
(
service
.
files
()
.
update
(
fileId
=
file_id
,
addParents
=
folder_id
,
removeParents
=
previous_parents
,
fields
=
"id, parents"
,
)
.
execute
()
)
return
file
.
get
(
"parents"
)
except
HttpError
as
error
:
print
(
f
"An error occurred:
{
error
}
"
)
return
None
if
__name__
==
"__main__"
:
move_file_to_folder
(
file_id
=
"1KuPmvGq8yoYgbfW74OENMCB5H0n_2Jm9"
,
folder_id
=
"1jvTFoyBhUspwDncOTB25kb9k0Fl0EqeN"
,
)
```


```
import
{
GoogleAuth
}
from
'google-auth-library'
;
import
{
google
}
from
'googleapis'
;
/**
* Moves a file to a new folder in Google Drive.
* @param {string} fileId The ID of the file to move.
* @param {string} folderId The ID of the folder to move the file to.
* @return {Promise<number>} The status of the move operation.
*/
async
function
moveFileToFolder
(
fileId
,
folderId
)
{
// Authenticate with Google and get an authorized client.
// TODO (developer): Use an appropriate auth mechanism for your app.
const
auth
=
new
GoogleAuth
({
scopes
:
'https://www.googleapis.com/auth/drive'
,
});
// Create a new Drive API client (v3).
const
service
=
google
.
drive
({
version
:
'v3'
,
auth
});
// Get the file's metadata to retrieve its current parents.
const
file
=
await
service
.
files
.
get
({
fileId
,
fields
:
'parents'
,
});
// Get the current parents as a comma-separated string.
const
previousParents
=
(
file
.
data
.
parents
??
[]).
join
(
','
);
// Move the file to the new folder.
const
result
=
await
service
.
files
.
update
({
fileId
,
addParents
:
folderId
,
removeParents
:
previousParents
,
fields
:
'id, parents'
,
});
// Print the status of the move operation.
console
.
log
(
result
.
status
);
return
result
.
status
;
}
```


```
<
?php
use Google\Client;
use Google\Service\Drive;
use Google\Service\Drive\DriveFile;
function moveFileToFolder($fileId,$folderId)
{
try {
$client = new Client();
$client->useApplicationDefaultCredentials();
$client->addScope(Drive::DRIVE);
$driveService = new Drive($client);
$emptyFileMetadata = new DriveFile();
// Retrieve the existing parents to remove
$file = $driveService->files->get($fileId, array('fields' => 'parents'));
$previousParents = join(',', $file->parents);
// Move the file to the new folder
$file = $driveService->files->update($fileId, $emptyFileMetadata, array(
'addParents' => $folderId,
'removeParents' => $previousParents,
'fields' => 'id, parents'));
return $file->parents;
} catch(Exception $e) {
echo "Error Message: ".$e;
}
}
```


```
using
Google
;
using
Google.Apis.Auth.OAuth2
;
using
Google.Apis.Drive.v3
;
using
Google.Apis.Services
;
namespace
DriveV3Snippets
{
// Class to demonstrate use-case of Drive move file to folder.
public
class
MoveFileToFolder
{
/// <summary>
/// Move specified file to the specified folder.
/// </summary>
/// <param name="fileId">Id of file to be moved.</param>
/// <param name="folderId">Id of folder where the fill will be moved.</param>
/// <returns>list of parent ids for the file, null otherwise.</returns>
public
static
IList<string>
DriveMoveFileToFolder
(
string
fileId
,
string
folderId
)
{
try
{
/* Load pre-authorized user credentials from the environment.
TODO(developer) - See https://developers.google.com/identity for
guides on implementing OAuth2 for your application. */
GoogleCredential
credential
=
GoogleCredential
.
GetApplicationDefault
()
.
CreateScoped
(
DriveService
.
Scope
.
Drive
);
// Create Drive API service.
var
service
=
new
DriveService
(
new
BaseClientService
.
Initializer
{
HttpClientInitializer
=
credential
,
ApplicationName
=
"Drive API Snippets"
});
// Retrieve the existing parents to remove
var
getRequest
=
service
.
Files
.
Get
(
fileId
);
getRequest
.
Fields
=
"parents"
;
var
file
=
getRequest
.
Execute
();
var
previousParents
=
String
.
Join
(
","
,
file
.
Parents
);
// Move the file to the new folder
var
updateRequest
=
service
.
Files
.
Update
(
new
Google
.
Apis
.
Drive
.
v3
.
Data
.
File
(),
fileId
);
updateRequest
.
Fields
=
"id, parents"
;
updateRequest
.
AddParents
=
folderId
;
updateRequest
.
RemoveParents
=
previousParents
;
file
=
updateRequest
.
Execute
();
return
file
.
Parents
;
}
catch
(
Exception
e
)
{
// TODO(developer) - handle error appropriately
if
(
e
is
AggregateException
)
{
Console
.
WriteLine
(
"Credential Not found"
);
}
else
if
(
e
is
GoogleApiException
)
{
Console
.
WriteLine
(
"File or Folder not found"
);
}
else
{
throw
;
}
}
return
null
;
}
}
}
```


## File and folder limits

Drive files and folders have some storage limits.


### User-item limit

Each user can have up to 500 million items that were created by that account.
When the limit is reached, the user can no longer create or upload items in
Drive. They can still view and edit existing items. To create
files again, users must permanently delete items or use a different account. For
more information, see
Trash or delete files and
folders
.

Objects that count toward this limit are:

- Items created or uploaded by the user in Drive
- Items created by the user but now owned by someone else
- Items in the trash
- Shortcuts
- Third-party shortcuts
Objects that don't count toward this limit are:

- Permanently-deleted items
- Items shared with the user but owned by someone else
- Items owned by the user but created by someone else
Attempts to add more than 500 million items returns an
activeItemCreationLimitExceeded
HTTP status code response.

Note that service accounts can't own any files. Instead, they must upload files
and folders into shared drives, or use OAuth 2.0 to upload items on behalf
of a human user.


### Folder-item limit

Each folder in a user's My Drive has a limit of 500,000 items.
This limit doesn't apply to the root folder of My Drive. Items
that count toward this limit are:

- Folders
- Files. All file types, regardless of file ownership.
- Shortcuts. Counts as a single item within a folder, even if the item it
points to isn't within that folder. For more information, see
Create a
shortcut to a Drive file
.
- Third-party shortcuts. Counts as a single item within a folder, even if the
item it points to isn't within that folder. For more information, see
Create a shortcut file to content stored by your
app
.
For more information about folder limits, see
Folder limits in
Google Drive
.


### Folder-depth limit

A user's My Drive can't contain more than 100 levels of nested
folders. This means that a child folder cannot be stored under a folder that's
more than 99 levels deep. This limitation only applies to child folders. A child
file with a
MIME type
other than
application/vnd.google-apps.folder
is exempt from this limitation.

For example, in the following diagram a new folder can be nested inside folder
number 99 but not inside folder number 100. However, folder number 100 can store
files like any other Drive folder:

Attempts to add more than 100 levels of folders returns a
myDriveHierarchyDepthLimitExceeded
HTTP status code response.


## Related topics

- Create and manage files
- Manage file metadata
- File and folder limits in shared drives
Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2026-04-20 UTC.


---

# Resolve errors Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/guides/handle-errors

- Home
- Google Workspace
- Google Drive
- Guides
The Google Drive API returns two levels of error information:

- HTTP error codes and header messages.
- A JSON object in the response body with additional details that can help you
determine how to handle the error.
Google Drive apps should catch and handle all errors that might be encountered
when using the REST API. This guide provides instructions about how to resolve
specific Drive API errors.


## HTTP status code summary


| Error code | Description |
| --- | --- |
| 200 - OK | The request is successful (this is the standard response for successful HTTP requests). |
| 400 - Bad Request | The request cannot be fulfilled due to a client error in the request. |
| 401 - Unauthorized | The request contains invalid credentials. |
| 403 - Forbidden | The request was received and understood, but the user doesn't have permission to perform the request. |
| 404 - Not Found | The requested page couldn't be found. |
| 429 - Too Many Requests | Too many requests to the API. |
| 500, 502, 503, 504 - Server Errors | Unexpected error arises while processing the request. |


## 400 errors

These errors mean that the request was unacceptable, often due to a missing
required parameter.


### badRequest

This error can occur from any one of the following issues in your code:

- A required field or parameter hasn't been provided.
- The value supplied or a combination of provided fields is invalid.
- You tried to add a duplicate parent to a Drive file.
- You tried to add a parent that would create a cycle in the directory graph.
The following JSON sample is a representation of this error:


```
{
"error"
:
{
"code"
:
400
,
"errors"
:
[
{
"domain"
:
"global"
,
"location"
:
"orderBy"
,
"locationType"
:
"parameter"
,
"message"
:
"Sorting is not supported for queries with fullText terms. Results are always in descending relevance order."
,
"reason"
:
"badRequest"
}
],
"message"
:
"Sorting is not supported for queries with fullText terms. Results are always in descending relevance order."
}
}
```

To fix this error, check the
message
field and adjust your code accordingly.


### illegalKeepForeverModification

This error occurs when trying to set a blob file revision marked as "Keep
Forever" to
false
. The following JSON sample is a representation of this
error:


```
{
"error"
:
{
"errors"
:
[
{
"domain"
:
"global"
,
"reason"
:
"illegalKeepForeverModification"
,
"message"
:
"Bad Request. Cannot update a revision to false that is marked as keepForever."
}
],
"code"
:
400
,
"message"
:
"Bad Request. Cannot update a revision to false that is marked as keepForever."
}
}
```

To fix this error, permanently delete a blob file revision to remove the "Keep
Forever" setting.


### invalidSharingRequest

This error occurs for several reasons. To determine the cause, evaluate the
reason
field of the returned JSON. This error most commonly occurs because:

- Sharing succeeded, but the notification email wasn't correctly delivered.
- The Access Control List (ACL) change isn't allowed for this user.
The
message
field indicates the actual error.


#### Share succeeded, but the notification email wasn't correctly delivered


```
{
"error"
:
{
"errors"
:
[
{
"domain"
:
"global"
,
"reason"
:
"invalidSharingRequest"
,
"message"
:
"Bad Request. User message: \"Sorry, the items were successfully shared but emails could not be sent to email@domain.com.\""
}
],
"code"
:
400
,
"message"
:
"Bad Request"
}
}
```

To fix this error, inform the user (sharer) they were unable to share because
the notification email couldn't be sent to the destination email address. The
user should make sure they have the correct email address and that it can
receive email.


#### The ACL change isn't allowed for this user


```
{
"error"
:
{
"errors"
:
[
{
"domain"
:
"global"
,
"reason"
:
"invalidSharingRequest"
,
"message"
:
"Bad Request. User message: \"ACL change not allowed.\""
}
],
"code"
:
400
,
"message"
:
"Bad Request"
}
}
```

To fix this error, check the
sharing
settings
of the Google Workspace
domain to which the file belongs. The settings might prohibit sharing outside of
the domain or sharing a shared drive might not be permitted.


## 401 errors

These errors mean the request doesn't contain a valid access token.


### authError

This error occurs when the access token that you're using is either expired or
invalid. This error can also be caused by missing authorization for the
requested scopes. The following JSON sample is a representation of this error:


```
{
"error"
:
{
"errors"
:
[
{
"domain"
:
"global"
,
"reason"
:
"authError"
,
"message"
:
"Invalid Credentials"
,
"locationType"
:
"header"
,
"location"
:
"Authorization"
,
}
],
"code"
:
401
,
"message"
:
"Invalid Credentials"
}
}
```

To fix this error, refresh the access token using the long-lived refresh token.
If this fails, direct the user through the OAuth flow, as described in
Choose
Google Drive API scopes
.


### fileNotDownloadable

This error occurs when you try to use the
revisions.get
method with the
alt=media
URL parameter on a Google Workspace document. The following JSON
sample is a representation of this error:


```
{
"error"
:
{
"errors"
:
[
{
"domain"
:
"global"
,
"reason"
:
"fileNotDownloadable"
,
"message"
:
"Only files with binary content can be downloaded. Use Export with Docs Editors files."
}
],
"code"
:
403
,
"message"
:
"Only files with binary content can be downloaded. Use Export with Docs Editors files."
}
}
```

To fix this error, try any of the following:

- Remove the
alt=media
URL parameter if you want to view the metadata of a
particular revision, such as the mimetype.
- Use the
files.export
method to export Google Workspace document byte
content. For more information, see
Export Google Workspace document
content
.

## 403 errors

These errors mean that a usage limit has been exceeded or the user doesn't have
the correct privileges. To determine the cause, evaluate the
reason
field of
the returned JSON.

For information about Drive API limits, refer to
Usage limits
. For information about Drive folder
limits, refer to
File and folder limits
.


### activeItemCreationLimitExceeded

An
activeItemCreationLimitExceeded
error occurs when the limit for the number
of items created per account has been exceeded. Each user can have up to 500
million items created by an account. For more information, see
User-item
limit
.


```
{
"error"
:
{
"errors"
:
[
{
"domain"
:
"global"
,
"reason"
:
"activeItemCreationLimitExceeded"
,
"message"
:
"This account has exceeded the creation limit of 500 million items. To create more items, permanently delete some items."
}
],
"code"
:
403
,
"message"
:
"This account has exceeded the creation limit of 500 million items. To create more items, permanently delete some items."
}
}
```

To fix this error:

- Inform the user that Drive prevents accounts from creating
more than 500 million items.
Inform the user that Drive prevents accounts from creating
more than 500 million items.

- If the user must create items in this same account, instruct them to
permanently delete some objects. Otherwise, they can use a different account
that already meets the requirement.
If the user must create items in this same account, instruct them to
permanently delete some objects. Otherwise, they can use a different account
that already meets the requirement.


### appNotAuthorizedToFile

This error occurs when your app isn't on the ACL for the file. This error
prevents the user from opening the file with your app. The following JSON sample
is a representation of this error:


```
{
"error"
:
{
"errors"
:
[
{
"domain"
:
"global"
,
"reason"
:
"appNotAuthorizedToFile"
,
"message"
:
"The user has not granted the app {appId} {verb} access to the file {fileId}."
}
],
"code"
:
403
,
"message"
:
"The user has not granted the app {appId} {verb} access to the file {fileId}."
}
}
```

- Open the Google Drive picker
and prompt the user to open the file.
- Instruct the user to open the file using the
Open with
context menu in the Drive
UI of your app.
- Use the
files.get
method to check the
isAppAuthorized
field on the
files
resource
to verify that your app created or opened the file.

### cannotModifyInheritedTeamDrivePermission

This error occurs when a user tries to modify the inherited permissions of an
item within a shared drive. Inherited permissions can't be removed from an item
in a shared drive. The following JSON sample is a representation of this error:


```
{
"error"
:
{
"errors"
:
[
{
"domain"
:
"global"
,
"reason"
:
"cannotModifyInheritedTeamDrivePermission"
,
"message"
:
"Cannot update or delete an inherited permission on a shared drive item."
}
],
"code"
:
403
,
"message"
:
"Cannot update or delete an inherited permission on a shared drive item."
}
}
```

To fix this error, a user must adjust the permissions on the direct or indirect
parent item from which they were inherited. For more information, see
How
permissions work
. You can
also retrieve the
permissions
resource to
see whether the permissions on this shared drive item are inherited or applied
directly.


### dailyLimitExceeded

This error occurs when the API limit for your project was reached. The following
JSON sample is a representation of this error:


```
{
"error"
:
{
"errors"
:
[
{
"domain"
:
"usageLimits"
,
"reason"
:
"dailyLimitExceeded"
,
"message"
:
"Daily Limit Exceeded"
}
],
"code"
:
403
,
"message"
:
"Daily Limit Exceeded"
}
}
```

This error appears when the application's owner has set a quota limit to cap
usage of a particular resource. To fix this error,
remove any usage caps for
the "Queries per day"
quota
.


### domainPolicy

This error occurs when the policy for the user's domain doesn't allow access to
Drive by your app. The following JSON sample is a representation
of this error:


```
{
"error"
:
{
"errors"
:
[
{
"domain"
:
"global"
,
"reason"
:
"domainPolicy"
,
"message"
:
"The domain administrators have disabled Drive apps."
}
],
"code"
:
403
,
"message"
:
"The domain administrators have disabled Drive apps."
}
}
```

- Inform the user that the domain doesn't allow your app to access files in
Drive.
- Instruct the user to contact the domain administrator to request access for
your app.

### downloadRestrictedForRevision

This error occurs when the user cannot download a blob file revision. The
following JSON sample is a representation of this error:


```
{
"error"
:
{
"errors"
:
[
{
"domain"
:
"global"
,
"reason"
:
"download_restricted_for_revision"
,
"message"
:
"This revision cannot be downloaded by the authenticated user."
}
],
"code"
:
403
,
"message"
:
"This revision cannot be downloaded by the authenticated user."
}
}
```

To fix this error, inform the user that the only way to download blob file
revisions is if they're marked as "Keep Forever". For more information, see
Specify revisions to save from auto
delete
.


### fileNotExportable

This error occurs when the user attempts to export a Google Vids file. The
following JSON sample is a representation of this error:


```
{
"error"
:
{
"errors"
:
[
{
"domain"
:
"global"
,
"reason"
:
"fileNotExportable"
,
"message"
:
"Google Vids does not support files.export. Use files.download with Vids files."
}
],
"code"
:
403
,
"message"
:
"Google Vids does not support files.export. Use files.download with Vids files."
}
}
```

To fix this error, inform the user that Google Vids files must be downloaded
with the
files.download
method, as the
files.export
method isn't supported.
For more information, see
Download and export files
.


### fileOwnerNotMemberOfTeamDrive

This error occurs when attempting to move a file into a shared drive and the
file owner isn't a member. The following JSON sample is a representation of this
error:


```
{
"error"
:
{
"errors"
:
[
{
"domain"
:
"global"
,
"reason"
:
"fileOwnerNotMemberOfTeamDrive"
,
"message"
:
"Cannot move a file into a shared drive as a writer when the owner of the file is not a member of that shared drive."
}
],
"code"
:
403
,
"message"
:
"Cannot move a file into a shared drive as a writer when the owner of the file is not a member of that shared drive."
}
}
```

- Add the member to the shared drive with
role=owner
. For more information,
see
Share files, folders, and drives
.
Add the member to the shared drive with
role=owner
. For more information,
see
Share files, folders, and drives
.

- Add the file to the shared drive. For more information, see
Create and
populate folders
.
Add the file to the shared drive. For more information, see
Create and
populate folders
.


### fileWriterTeamDriveMoveInDisabled

This error occurs when a domain administrator hasn't allowed users with
role=writer
to move items into a shared drive. The user attempting to move the
items has fewer permissions than allowed on the destination shared drive. The
following JSON sample is a representation of this error:


```
{
"error"
:
{
"errors"
:
[
{
"domain"
:
"global"
,
"reason"
:
"fileWriterTeamDriveMoveInDisabled"
,
"message"
:
"The domain administrator has not allowed writers to move items into a shared drive."
}
],
"code"
:
403
,
"message"
:
"The domain administrator has not allowed writers to move items into a shared drive."
}
}
```

To fix this error, use the same administrator user account on both the source
and destination shared drives.


### insufficientFilePermissions

This error occurs when the user doesn't have write access to a file, and your
app is attempting to modify the file. The following JSON sample is a
representation of this error:


```
{
"error"
:
{
"errors"
:
[
{
"domain"
:
"global"
,
"reason"
:
"insufficientFilePermissions"
,
"message"
:
"The user does not have sufficient permissions for file {fileId}."
}
],
"code"
:
403
,
"message"
:
"The user does not have sufficient permissions for file {fileId}."
}
}
```

To fix this error, instruct the user to contact the file's owner and request
edit access. You can also check user access levels in the metadata retrieved by
the
files.get
method and display a read-only
UI when permissions are missing.


### myDriveHierarchyDepthLimitExceeded

A
myDriveHierarchyDepthLimitExceeded
error occurs when the limit for the
number of nested folder levels has been exceeded. A user's My
Drive can't contain more than 100 levels of nested folders. For
more information, see
Folder-depth limit
.


```
{
"error"
:
{
"errors"
:
[
{
"domain"
:
"global"
,
"reason"
:
"myDriveHierarchyDepthLimitExceeded"
,
"message"
:
"Your My Drive can't contain more than 100 levels of folders. For details, see https://developers.google.com/workspace/drive/api/guides/handle-errors#nested-folder-levels."
}
],
"code"
:
403
,
"message"
:
"Your My Drive can't contain more than 100 levels of folders. For details, see https://developers.google.com/workspace/drive/api/guides/handle-errors#nested-folder-levels."
}
}
```

- Inform the user that Drive prevents placing folders more than
100 levels deep.
- If the user must create another nested folder, instruct them to reorganize
the intended parent folder to be fewer than 100 levels deep or use a
different parent folder that already meets the requirement.

### numChildrenInNonRootLimitExceeded

This error occurs when the limit for a folder's number of children (folders,
files, and shortcuts) has been exceeded. There's a 500,000 item limit for
folders, files, and shortcuts directly in a folder. Items nested in subfolders
don't count against this 500,000 item limit. For more information on
Drive folder limits, refer to
Folder limits in
Google Drive
.


```
{
"error"
:
{
"errors"
:
[
{
"domain"
:
"global"
,
"reason"
:
"numChildrenInNonRootLimitExceeded"
,
"message"
:
"The limit for this folder's number of children (files and folders) has been exceeded."
}
],
"code"
:
403
,
"message"
:
"The limit for this folder's number of children (files and folders) has been exceeded."
}
}
```

- Inform the user that Drive prevents folders with more than
500,000 items.
- If the user must add more items to the full folder, instruct them to
reorganize the folder to contain fewer than 500,000 items or use a similar
folder that already contains fewer items.

### rateLimitExceeded

This error occurs when the project's rate limit has been reached. This limit
varies depending on the type of request. The following JSON sample is a
representation of this error:


```
{
"error"
:
{
"errors"
:
[
{
"domain"
:
"usageLimits"
,
"message"
:
"Rate Limit Exceeded"
,
"reason"
:
"rateLimitExceeded"
,
}
],
"code"
:
403
,
"message"
:
"Rate Limit Exceeded"
}
}
```

- Raise the per-user quota in the Google Cloud project. For more information,
request a quota increase
.
- Batch requests
to bundle
multiple API calls into one HTTP request.
- Use
exponential backoff
to retry the
request.

### sharingRateLimitExceeded

This error occurs when the user reaches a sharing limit and is often linked with
an email limit. The following JSON sample is a representation of this error:


```
{
"error"
:
{
"errors"
:
[
{
"domain"
:
"global"
,
"message"
:
"Rate limit exceeded. User message: \"These item(s) could not be shared because a rate limit was exceeded: filename"
,
"reason"
:
"sharingRateLimitExceeded"
,
}
],
"code"
:
403
,
"message"
:
"Rate Limit Exceeded"
}
}
```

- Don't send emails when sharing large amounts of files.
- If one user is making numerous requests on behalf of many users of a
Google Workspace account, consider a
service account with domain-wide
delegation
using the
quotaUser
parameter
.

### storageQuotaExceeded

This error occurs when the user reaches their storage limit. The following JSON
sample is a representation of this error:


```
{
"error"
:
{
"errors"
:
[
{
"domain"
:
"global"
,
"message"
:
"The user's Drive storage quota has been exceeded."
,
"reason"
:
"storageQuotaExceeded"
,
}
],
"code"
:
403
,
"message"
:
"The user's Drive storage quota has been exceeded."
}
}
```

- Review your Drive account storage limits. For more
information, refer to
Google Workspace storage and upload
limits
.
Review your Drive account storage limits. For more
information, refer to
Google Workspace storage and upload
limits
.

- Manage your storage in Drive, Gmail &
Google Photos
.
Manage your storage in Drive, Gmail &
Google Photos
.

- Buy more Google storage
.
Buy more Google storage
.


### teamDriveFileLimitExceeded

This error occurs when a user attempts to exceed the strict item limit on a
shared drive. Each folder in a user's shared drive has a limit of 500,000 items,
including files, folders, and shortcuts. This limit is based on item count, not
storage use. For more information, see
Shared drive limits in
Google Drive
.


```
{
"error"
:
{
"errors"
:
[
{
"domain"
:
"global"
,
"reason"
:
"teamDriveFileLimitExceeded"
,
"message"
:
"The file limit for this shared drive has been exceeded."
}
],
"code"
:
403
,
"message"
:
"The file limit for this shared drive has been exceeded."
}
}
```

To fix this error, reduce the number of items in the shared drive. Shared drives
with too many files might be difficult to organize and search.


### teamDriveHierarchyTooDeep

A
teamDriveHierarchyTooDeep
error occurs when the limit for the number of
shared drive nested folder levels has been exceeded. A user's shared drive can't
contain more than 100 levels of nested folders. For more information, see
Folder-depth limit
.


```
{
"error"
:
{
"errors"
:
[
{
"domain"
:
"global"
,
"reason"
:
"teamDriveHierarchyTooDeep"
,
"message"
:
"The shared drive hierarchy depth will exceed the limit."
}
],
"code"
:
403
,
"message"
:
"The shared drive hierarchy depth will exceed the limit."
}
}
```

- Inform the user that shared drives prevents placing folders more than
100 levels deep.

### teamDriveMembershipRequired

This error occurs when a user attempts to access a shared drive in which they're
not a member. The following JSON sample is a representation of this error:


```
{
"error"
:
{
"errors"
:
[
{
"domain"
:
"global"
,
"reason"
:
"teamDriveMembershipRequired"
,
"message"
:
"The attempted action requires shared drive membership."
}
],
"code"
:
403
,
"message"
:
"The attempted action requires shared drive membership."
}
}
```

- Ask the manager of the shared drive to add you with the appropriate
permissions for the action you must perform.
Ask the manager of the shared drive to add you with the appropriate
permissions for the action you must perform.

- Review Drive's
roles and
permissions
to learn who can access and manage
shared drives. Additional information about access levels can also be found
at
Create a shared
drive
.
Review Drive's
roles and
permissions
to learn who can access and manage
shared drives. Additional information about access levels can also be found
at
Create a shared
drive
.


### teamDrivesFolderMoveInNotSupported

This error occurs when a user attempts to move a folder from My
Drive into a shared drive. The following JSON sample is a
representation of this error:


```
{
"error"
:
{
"errors"
:
[
{
"domain"
:
"global"
,
"reason"
:
"teamDrivesFolderMoveInNotSupported"
,
"message"
:
"Moving folders into shared drives is not supported."
}
],
"code"
:
403
,
"message"
:
"Moving folders into shared drives is not supported."
}
}
```

- Move the individual items from the folder into a shared drive using the
Drive API. Set the
supportsAllDrives=true
parameter to denote the
support of both My Drive and shared drives.
Move the individual items from the folder into a shared drive using the
Drive API. Set the
supportsAllDrives=true
parameter to denote the
support of both My Drive and shared drives.

- If you must move the folder into a shared drive, use the
Drive UI. For more information, see
Move folders into shared
drives as an admin
.
If you must move the folder into a shared drive, use the
Drive UI. For more information, see
Move folders into shared
drives as an admin
.


### teamDrivesParentLimit

This error occurs when a user attempts to add more than one parent to an item in
a shared drive. The following JSON sample is a representation of this error:


```
{
"error"
:
{
"errors"
:
[
{
"domain"
:
"global"
,
"reason"
:
"teamDrivesParentLimit"
,
"message"
:
"A shared drive item must have exactly one parent."
}
],
"code"
:
403
,
"message"
:
"A shared drive item must have exactly one parent."
}
}
```

To fix this error, use Drive shortcuts to add multiple links to a
file. Although a shortcut can only have one parent, a shortcut file can be
copied to the additional locations. For more information, see
Create a shortcut
to a Drive file
.


### UrlLeaseLimitExceeded

This error occurs when trying to save Google Play game data through your
application. The following JSON sample is a representation of this error:


```
{
"error"
:
{
"errors"
:
[
{
"domain"
:
"usageLimits"
,
"reason"
:
"UrlLeaseLimitExceeded"
,
"message"
:
"Too many pending uploads for this snapshot. Please finish or cancel some before creating more."
}
],
"code"
:
403
,
"message"
:
"Too many pending uploads for this snapshot. Please finish or cancel some before creating more."
}
}
```

To fix this error, complete or cancel any uploads for a snapshot before creating
more.


### userRateLimitExceeded

This error occurs when the per-user limit has been reached. This might be a
limit from the Google Cloud console or a limit from the Drive
backend. The following JSON sample is a representation of this error:


```
{
"error"
:
{
"errors"
:
[
{
"domain"
:
"usageLimits"
,
"reason"
:
"userRateLimitExceeded"
,
"message"
:
"User Rate Limit Exceeded"
}
],
"code"
:
403
,
"message"
:
"User Rate Limit Exceeded"
}
}
```

Raise the per-user quota in the Google Cloud project. For more information,
request a quota increase
.

If one user is making numerous requests on behalf of many users of a
Google Workspace account, consider a
service account with domain-wide
delegation
using the
quotaUser
parameter
.

Use
exponential backoff
to retry the
request.

For information about Drive API limits, refer to
Usage limits
.


## 404 errors

These errors mean that the requested resource isn't accessible or doesn't exist.


### notFound

This error occurs when the user doesn't have read access to a file, or the file
doesn't exist. The following JSON sample is a representation of this error:


```
{
"error"
:
{
"errors"
:
[
{
"domain"
:
"global"
,
"reason"
:
"notFound"
,
"message"
:
"File not found {fileId}"
}
],
"code"
:
404
,
"message"
:
"File not found: {fileId}"
}
}
```

- If the file is located in a shared drive, and you're using the
files.get
method, make sure the
supportsAllDrives
query parameter is set to
true
.
- Inform the user that they don't have read access to the file or the file
doesn't exist.
- Instruct the user to contact the file's owner and request permission to the
file.

## 429 errors

These errors mean that too many requests were sent to the API too quickly.

This error occurs when the user has sent too many requests in a given amount of
time. The following JSON sample is a representation of this error:


```
{
"error"
:
{
"errors"
:
[
{
"domain"
:
"usageLimits"
,
"reason"
:
"rateLimitExceeded"
,
"message"
:
"Rate Limit Exceeded"
}
],
"code"
:
429
,
"message"
:
"Rate Limit Exceeded"
s
}
}
```

To fix this error, use
exponential backoff
to retry the request.


## 500, 502, 503, 504 errors

These errors occur when an unexpected server error arises while processing the
request. Various issues can cause these errors, including a request's timing
overlapping with another request or a request for an unsupported action, such as
attempting to update permissions for a single page in Google Sites instead of
the entire site.

The following is a list of 5xx errors:

- 500 Backend error
- 502 Bad Gateway
- 503 Service Unavailable
- 504 Gateway Timeout

## Related topics

- Improve performance
- Troubleshoot authentication and authorization issues
Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2026-04-20 UTC.


---

# Integrate with Drive UI's "New" button Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/guides/integrate-create

- Home
- Google Workspace
- Google Drive
- Guides
When a user clicks
Drive UI's "New"
button
and selects an app in the
Drive UI, Drive redirects the user to that app's New URL
defined in
Configure a Drive UI
integration
.

Your app then receives a default set of template variables within a
state
parameter. The default
state
information for a New URL is:


```
{
  "action":"create",
  "folderId":"
FOLDER_ID
",
  "folderResourceKey":"
FOLDER_RESOURCE_KEY
",
  "userId":"
USER_ID
"
}
```

This output includes the following values:

- create
: The action being performed. The value is
create
when a user
clicks
Drive UI's "New"
button
.
- FOLDER_ID
: The ID of the parent folder.
- FOLDER_RESOURCE_KEY
: The resource key of the parent folder.
- USER_ID
: The profile ID that uniquely identifies the
 user.
Your app must act on this request by following these steps:

- Verify that the
action
field has a value of
create
.
- Use the
userId
value to create a new session for the user. For more
information on signed-in users, see
Users & new events
.
- Use the
files.create
method to
create a file resource. If
folderId
was set on the request, set the
parents
field to the
folderId
value.
- If
folderResourceKey
was set on the request, set the
X-Goog-Drive-Resource-Keys
request header. For more information on
resource keys, see
Access link-shared files using resource
keys
.
The
state
parameter is URL-encoded, so your app must handle the escape
characters and parse it as JSON.


## Users & new events

Drive apps should treat all "create" events as potential
sign-ins. Some users might have multiple accounts, so the user ID in the
state
parameter might not match the current session. If the user ID in the
state
parameter doesn't match the current session, end the current session for your
app and sign in as the requested user.

Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2026-04-23 UTC.


---

# Integrate with Drive UI's "Open with" context menu Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/guides/integrate-open

- Home
- Google Workspace
- Google Drive
- Guides
When a user selects a file and clicks the
Drive UI's "Open with"
menu item
, Drive redirects
the user to that app's Open URL defined in
Configure a Drive UI
integration
.

If you checked the "Importing" box when you configured a Drive UI
integration, the user can select a combination of app-specific and
Google Workspace files to open. When you configure a Drive UI
integration, app-specific files are defined in the "Default MIME types" and
"Default file extensions" fields, whereas Google Workspace
files are defined in the "Secondary MIME types" and "Secondary file extensions"
fields.

For each file that the user wants to open, Drive checks the MIME
types against your defined default and secondary MIME types:

- For MIME types defined in the "Default MIME types" field, the file ID is
passed to your app. For information on how to handle app-specific files,
see
Handle an Open URL for app-specific documents
.
For MIME types defined in the "Default MIME types" field, the file ID is
passed to your app. For information on how to handle app-specific files,
see
Handle an Open URL for app-specific documents
.

- For MIME types defined in the "Secondary MIME types" field, the
Drive UI displays a dialog asking the user what file type to
convert the Google Workspace file to. For example, if you select a
Google Docs file in the Drive UI and the "Secondary MIME
types" field suggests your app supports text/plain or application/pdf, the
Drive UI asks the user if they want to convert to Plain Text
or PDF.
For information on how to handle Google Workspace
files, see
Handle an Open URL for Google Workspace documents
.
For a list of Google Workspace documents and MIME type conversion formats,
see
Export MIME types for Google Workspace
documents
.
For MIME types defined in the "Secondary MIME types" field, the
Drive UI displays a dialog asking the user what file type to
convert the Google Workspace file to. For example, if you select a
Google Docs file in the Drive UI and the "Secondary MIME
types" field suggests your app supports text/plain or application/pdf, the
Drive UI asks the user if they want to convert to Plain Text
or PDF.

For information on how to handle Google Workspace
files, see
Handle an Open URL for Google Workspace documents
.
For a list of Google Workspace documents and MIME type conversion formats,
see
Export MIME types for Google Workspace
documents
.


## Handle an Open URL for app-specific documents

As mentioned in
Configure a Drive UI
integration
,
your app receives template variables with information for your app to open
the file. Your app receives a default set of template variables
within a
state
parameter. The
default
state
information for an app-specific Open URL is:


```
{
  "ids": ["
ID
"],
  "resourceKeys":{"
RESOURCE_KEYS
":"
RESOURCE_KEYS
"},
  "action":"open",
  "userId":"
USER_ID
"
}
```

This output includes the following values:

- ID
: The ID of the parent folder.
- RESOURCE_KEYS
: A JSON dictionary of file IDs mapped to
their respective resource keys.
- open
: The action being performed. The value is
open
when using an Open
URL.
- USER_ID
: The profile ID that uniquely identifies the user.
Your app must act on this request by following these steps:

- Verify that the
action
field has a value of
open
and the
ids
field is
present.
- Use the
userId
value to create a new session for the user. For more
information on signed-in users, see
Users & new events
.
- Use the
files.get
method to check
permissions, fetch file metadata, and download the file content using
the
ID
values.
- If
resourceKeys
was set on the request, set the
X-Goog-Drive-Resource-Keys
request header. For more information on
resource keys, see
Access link-shared files using resource
keys
.
The
state
parameter is URL-encoded, so your app must handle the escape
characters and parse it as JSON.


## Handle an Open URL for Google Workspace documents

As mentioned in
Configure a Drive UI
integration
, your app receives a default set of
template variables within a
state
parameter. The default
state
information
for a Google Workspace Open URL is:


```
{
"exportIds"
:
[
"
ID
"
],
"resourceKeys"
:{
"
RESOURCE_KEYS
"
:
"
RESOURCE_KEYS
"
},
"action"
:
"open"
,
"userId"
:
"
USER_ID
"
}
```

- EXPORT_ID
: A comma-separated list of file IDs being
exported. Used only when opening Google Workspace files.
- USER_ID
: The profile ID that identifies the user.
- Verify that this is a request to open a file by detecting both the
open
value in the
state
field and the presence of the
exportIds
field.
Verify that this is a request to open a file by detecting both the
open
value in the
state
field and the presence of the
exportIds
field.

- Use the
files.get
method to check
permissions, fetch file metadata, and determine the MIME type using the
EXPORT_ID
values.
Use the
files.get
method to check
permissions, fetch file metadata, and determine the MIME type using the
EXPORT_ID
values.

- Convert the file content using the
files.export
method. The following
code sample shows how to export a Google Workspace document to the
requested MIME type.
Convert the file content using the
files.export
method. The following
code sample shows how to export a Google Workspace document to the
requested MIME type.

- If
resourceKey
was set on the request, set the
X-Goog-Drive-Resource-Keys
request header. For more information on
resource keys, see
Access link-shared files using resource
keys
.
Java
drive/snippets/drive_v3/src/main/java/ExportPdf.java
View on GitHub
import
com.google.api.client.googleapis.json.GoogleJsonResponseException
;
import
com.google.api.client.http.HttpRequestInitializer
;
import
com.google.api.client.http.javanet.NetHttpTransport
;
import
com.google.api.client.json.gson.GsonFactory
;
import
com.google.api.services.drive.Drive
;
import
com.google.api.services.drive.DriveScopes
;
import
com.google.auth.http.HttpCredentialsAdapter
;
import
com.google.auth.oauth2.GoogleCredentials
;
import
java.io.ByteArrayOutputStream
;
import
java.io.IOException
;
import
java.io.OutputStream
;
import
java.util.Arrays
;
/* Class to demonstrate use-case of drive's export pdf. */
public
class
ExportPdf
{
/**
* Download a Document file in PDF format.
*
* @param realFileId file ID of any workspace document format file.
* @return byte array stream if successful, {@code null} otherwise.
* @throws IOException if service account credentials file not found.
*/
public
static
ByteArrayOutputStream
exportPdf
(
String
realFileId
)
throws
IOException
{
// Load pre-authorized user credentials from the environment.
// TODO(developer) - See https://developers.google.com/identity for
// guides on implementing OAuth2 for your application.
GoogleCredentials
credentials
=
GoogleCredentials
.
getApplicationDefault
()
.
createScoped
(
Arrays
.
asList
(
DriveScopes
.
DRIVE_FILE
));
HttpRequestInitializer
requestInitializer
=
new
HttpCredentialsAdapter
(
credentials
);
// Build a new authorized API client service.
Drive
service
=
new
Drive
.
Builder
(
new
NetHttpTransport
(),
GsonFactory
.
getDefaultInstance
(),
requestInitializer
)
.
setApplicationName
(
"Drive samples"
)
.
build
();
OutputStream
outputStream
=
new
ByteArrayOutputStream
();
try
{
service
.
files
().
export
(
realFileId
,
"application/pdf"
)
.
executeMediaAndDownloadTo
(
outputStream
);
return
(
ByteArrayOutputStream
)
outputStream
;
}
catch
(
GoogleJsonResponseException
e
)
{
// TODO(developer) - handle error appropriately
System
.
err
.
println
(
"Unable to export file: "
+
e
.
getDetails
());
throw
e
;
}
}
}
Python
drive/snippets/drive-v3/file_snippet/export_pdf.py
View on GitHub
import
io
import
google.auth
from
googleapiclient.discovery
import
build
from
googleapiclient.errors
import
HttpError
from
googleapiclient.http
import
MediaIoBaseDownload
def
export_pdf
(
real_file_id
):
"""Download a Document file in PDF format.
Args:
real_file_id : file ID of any workspace document format file
Returns : IO object with location
Load pre-authorized user credentials from the environment.
TODO(developer) - See https://developers.google.com/identity
for guides on implementing OAuth2 for the application.
"""
creds
,
_
=
google
.
auth
.
default
()
try
:
# create drive api client
service
=
build
(
"drive"
,
"v3"
,
credentials
=
creds
)
file_id
=
real_file_id
# pylint: disable=maybe-no-member
request
=
service
.
files
()
.
export_media
(
fileId
=
file_id
,
mimeType
=
"application/pdf"
)
file
=
io
.
BytesIO
()
downloader
=
MediaIoBaseDownload
(
file
,
request
)
done
=
False
while
done
is
False
:
status
,
done
=
downloader
.
next_chunk
()
print
(
f
"Download
{
int
(
status
.
progress
()
*
100
)
}
."
)
except
HttpError
as
error
:
print
(
f
"An error occurred:
{
error
}
"
)
file
=
None
return
file
.
getvalue
()
if
__name__
==
"__main__"
:
export_pdf
(
real_file_id
=
"1zbp8wAyuImX91Jt9mI-CAX_1TqkBLDEDcr2WeXBbKUY"
)
Node.js
drive/snippets/drive_v3/file_snippets/export_pdf.js
View on GitHub
import
{
GoogleAuth
}
from
'google-auth-library'
;
import
{
google
}
from
'googleapis'
;
/**
* Exports a Google Doc as a PDF.
* @param {string} fileId The ID of the file to export.
* @return {Promise<number>} The status of the export request.
*/
async
function
exportPdf
(
fileId
)
{
// Authenticate with Google and get an authorized client.
// TODO (developer): Use an appropriate auth mechanism for your app.
const
auth
=
new
GoogleAuth
({
scopes
:
'https://www.googleapis.com/auth/drive'
,
});
// Create a new Drive API client (v3).
const
service
=
google
.
drive
({
version
:
'v3'
,
auth
});
// Export the file as a PDF.
const
result
=
await
service
.
files
.
export
({
fileId
,
mimeType
:
'application/pdf'
,
});
// Print the status of the export.
console
.
log
(
result
.
status
);
return
result
.
status
;
}
PHP
drive/snippets/drive_v3/src/DriveExportPdf.php
View on GitHub
<
?php
use Google\Client;
use Google\Service\Drive;
function exportPdf()
{
try {
$client = new Client();
$client->useApplicationDefaultCredentials();
$client->addScope(Drive::DRIVE);
$driveService = new Drive($client);
$realFileId = readline("Enter File Id: ");
$fileId = '1ZdR3L3qP4Bkq8noWLJHSr_iBau0DNT4Kli4SxNc2YEo';
$fileId = $realFileId;
$response = $driveService->files->export($fileId, 'application/pdf', array(
'alt' => 'media'));
$content = $response->getBody()->getContents();
return $content;
} catch(Exception $e) {
echo "Error Message: ".$e;
}
}
If
resourceKey
was set on the request, set the
X-Goog-Drive-Resource-Keys
request header. For more information on
resource keys, see
Access link-shared files using resource
keys
.


### Java


```
import
com.google.api.client.googleapis.json.GoogleJsonResponseException
;
import
com.google.api.client.http.HttpRequestInitializer
;
import
com.google.api.client.http.javanet.NetHttpTransport
;
import
com.google.api.client.json.gson.GsonFactory
;
import
com.google.api.services.drive.Drive
;
import
com.google.api.services.drive.DriveScopes
;
import
com.google.auth.http.HttpCredentialsAdapter
;
import
com.google.auth.oauth2.GoogleCredentials
;
import
java.io.ByteArrayOutputStream
;
import
java.io.IOException
;
import
java.io.OutputStream
;
import
java.util.Arrays
;
/* Class to demonstrate use-case of drive's export pdf. */
public
class
ExportPdf
{
/**
* Download a Document file in PDF format.
*
* @param realFileId file ID of any workspace document format file.
* @return byte array stream if successful, {@code null} otherwise.
* @throws IOException if service account credentials file not found.
*/
public
static
ByteArrayOutputStream
exportPdf
(
String
realFileId
)
throws
IOException
{
// Load pre-authorized user credentials from the environment.
// TODO(developer) - See https://developers.google.com/identity for
// guides on implementing OAuth2 for your application.
GoogleCredentials
credentials
=
GoogleCredentials
.
getApplicationDefault
()
.
createScoped
(
Arrays
.
asList
(
DriveScopes
.
DRIVE_FILE
));
HttpRequestInitializer
requestInitializer
=
new
HttpCredentialsAdapter
(
credentials
);
// Build a new authorized API client service.
Drive
service
=
new
Drive
.
Builder
(
new
NetHttpTransport
(),
GsonFactory
.
getDefaultInstance
(),
requestInitializer
)
.
setApplicationName
(
"Drive samples"
)
.
build
();
OutputStream
outputStream
=
new
ByteArrayOutputStream
();
try
{
service
.
files
().
export
(
realFileId
,
"application/pdf"
)
.
executeMediaAndDownloadTo
(
outputStream
);
return
(
ByteArrayOutputStream
)
outputStream
;
}
catch
(
GoogleJsonResponseException
e
)
{
// TODO(developer) - handle error appropriately
System
.
err
.
println
(
"Unable to export file: "
+
e
.
getDetails
());
throw
e
;
}
}
}
```


### Python


```
import
io
import
google.auth
from
googleapiclient.discovery
import
build
from
googleapiclient.errors
import
HttpError
from
googleapiclient.http
import
MediaIoBaseDownload
def
export_pdf
(
real_file_id
):
"""Download a Document file in PDF format.
Args:
real_file_id : file ID of any workspace document format file
Returns : IO object with location
Load pre-authorized user credentials from the environment.
TODO(developer) - See https://developers.google.com/identity
for guides on implementing OAuth2 for the application.
"""
creds
,
_
=
google
.
auth
.
default
()
try
:
# create drive api client
service
=
build
(
"drive"
,
"v3"
,
credentials
=
creds
)
file_id
=
real_file_id
# pylint: disable=maybe-no-member
request
=
service
.
files
()
.
export_media
(
fileId
=
file_id
,
mimeType
=
"application/pdf"
)
file
=
io
.
BytesIO
()
downloader
=
MediaIoBaseDownload
(
file
,
request
)
done
=
False
while
done
is
False
:
status
,
done
=
downloader
.
next_chunk
()
print
(
f
"Download
{
int
(
status
.
progress
()
*
100
)
}
."
)
except
HttpError
as
error
:
print
(
f
"An error occurred:
{
error
}
"
)
file
=
None
return
file
.
getvalue
()
if
__name__
==
"__main__"
:
export_pdf
(
real_file_id
=
"1zbp8wAyuImX91Jt9mI-CAX_1TqkBLDEDcr2WeXBbKUY"
)
```


### Node.js


```
import
{
GoogleAuth
}
from
'google-auth-library'
;
import
{
google
}
from
'googleapis'
;
/**
* Exports a Google Doc as a PDF.
* @param {string} fileId The ID of the file to export.
* @return {Promise<number>} The status of the export request.
*/
async
function
exportPdf
(
fileId
)
{
// Authenticate with Google and get an authorized client.
// TODO (developer): Use an appropriate auth mechanism for your app.
const
auth
=
new
GoogleAuth
({
scopes
:
'https://www.googleapis.com/auth/drive'
,
});
// Create a new Drive API client (v3).
const
service
=
google
.
drive
({
version
:
'v3'
,
auth
});
// Export the file as a PDF.
const
result
=
await
service
.
files
.
export
({
fileId
,
mimeType
:
'application/pdf'
,
});
// Print the status of the export.
console
.
log
(
result
.
status
);
return
result
.
status
;
}
```


### PHP


```
<
?php
use Google\Client;
use Google\Service\Drive;
function exportPdf()
{
try {
$client = new Client();
$client->useApplicationDefaultCredentials();
$client->addScope(Drive::DRIVE);
$driveService = new Drive($client);
$realFileId = readline("Enter File Id: ");
$fileId = '1ZdR3L3qP4Bkq8noWLJHSr_iBau0DNT4Kli4SxNc2YEo';
$fileId = $realFileId;
$response = $driveService->files->export($fileId, 'application/pdf', array(
'alt' => 'media'));
$content = $response->getBody()->getContents();
return $content;
}  catch(Exception $e) {
echo "Error Message: ".$e;
}
}
```

Display converted files as read-only or present a dialog letting the user to
save the file as the new file type.


## Users & new events

Drive apps should treat all "open with" events as potential
sign-ins. Some users might have multiple accounts, so the user ID in the
state
parameter might not match the current session. If the user ID in the
state
parameter doesn't match the current session, end the current session for your
app and sign in as the requested user.


## Related topics

In addition to opening an application from Google Drive UI, applications can
display a file picker to select content from within an app. For more
information, see the
Google Picker
.

Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2026-04-23 UTC.


---

# Manage folders with limited and expansive access Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/guides/limited-expansive-access

- Home
- Google Workspace
- Google Drive
- Guides
A user owns a My Drive folder. The folder might contain multiple
users with access to different files. This restrictive access model means
different users could see different lists of items within the same folder. A
user with access to the parent My Drive folder but not to an item
within that folder has "restricted access". It creates a situation where it's
difficult to know who has access within the hierarchy.

Conversely, shared drive files are owned by the shared drive. Shared drives have
an expansive model so every user has the same list of items within the same
folder.

The introduction of
folders with limited access
replicates the expansive
access model from shared drives to My Drive. With this change,
folders with limited access are the one exception that allows restricting access
to a specific subfolder in both My Drive and shared drives.

This guide explains how you can manage folders with limited access and expansive
access in Google Drive.


## About folders with limited access

Folders with limited access allow you to restrict folders to specific users.
Only users you directly add to the folder's permissions can open it and access
its content. Users with inherited access to the shared My Drive
folder or shared drive folder (through access from a parent folder) can see the
restricted folder in Drive but can't open it. This feature better
aligns the sharing behavior of items in both My Drive and shared
drives, letting you organize folders with sensitive content alongside more
broadly shared content.

Folders with limited access are available in both My Drive and
shared drives. The
owner
role in My Drive and the
organizer
role in shared drives can always access folders with limited access. To modify
the list of folder users, no special permissions are required. Roles that can
share folders can update the member lists. To learn more about roles and
permissions, see
Roles and permissions
and
Shared
drives overview
.

Note that although
folders
are a type of
file, limited access isn't available for files.


### Set limited access on a folder

While users with direct folder permissions can access a folder with limited
access, only the
owner
role in My Drive and the
organizer
role in shared drives can enable or disable limited access.

Additionally, if a user with the
writer
role in My Drive has
the
writersCanShare
boolean field on the
files
resource set to
true
, they can also turn the feature on or off.

To limit access to a folder, set the boolean
inheritedPermissionsDisabled
field on the
files
resource to
true
. When
true
, only the
owner
role, the
organizer
role, and users with direct folder permissions can access it.

To turn inherited permissions back on, set
inheritedPermissionsDisabled
to
false
.


### Verify permission to limit access on a folder

To check if you can limit access to a folder or not, inspect the boolean values
of the
capabilities.canDisableInheritedPermissions
and
capabilities.canEnableInheritedPermissions
fields on the
files
resource. These settings confirm if you have
permission to limit access to a folder through the
inheritedPermissionsDisabled
field.

For more information about
capabilities
, see
Understand file capabilities
.


### List children of a folder with limited access

To check if you can list the children of a folder, use the
capabilities.canListChildren
boolean field.

The returned value is always
false
when the item isn't a folder or if the
requester's access to the folder's contents was removed by setting
inheritedPermissionsDisabled
to
false
.

If your access to the folder's contents was removed, you can still access the
folder
metadata
with the
files.get()
and
files.list()
methods. To confirm access is
limited, check the response body to see if the item is a folder with the
MIME
type
application/vnd.google-apps.folder
and the
capabilities.canListChildren
field is set to false. If you try to list the
children of such a folder, the result is always empty.


### Access folder with limited access metadata

Folders with limited access let you view folder
metadata
if you have no access to the folder contents.

When using the
permissions
resource to
determine a user's access, both My Drive and shared drive folders
that only grant access to the metadata contain the following values in the
response body:
inheritedPermissionsDisabled=true
and
view=metadata
. The role
is always set to
reader
. The
view
field is only populated for permissions
that belong to a
view
. For more information, see
Views
.

All the entries in the
permissionDetails
field have the
inherited
field set
to
true
to denote the permission is inherited and that direct access to the
folder contents hasn't been granted.

To grant access to both the folder contents and metadata, set the
inheritedPermissionsDisabled
field to
false
or update the role to
reader
or higher.

Finally, if a permission was first limited by turning off inheritance on a
folder (
inheritedPermissionsDisabled=true
), and then the permission was added
back directly to the folder, the values in the response body become
inheritedPermissionsDisabled=true
with the
view
field as unset. If the
folder is in a shared drive, the
permissionDetails
list has an entry with the
inherited
field set to
false
to denote the permission isn't inherited. This
permission grants access to both folder contents and metadata like any other
permission.


### Delete folders with limited access

You can delete folders with limited access using the
files.delete()
method on the
files
resource.

In My Drive, only the item's owner can delete a folder hierarchy.
If a user deletes a hierarchy with folders that have limited access and are
owned by others, these folders move to the owner's My Drive.

If the user has the
owner
role, the entire hierarchy gets deleted.

In shared drives, the
organizer
role can delete hierarchies even if they
contain folders with limited access. If the
fileOrganizer
role deletes a
hierarchy that contains folders with limited access, the result depends on if
they were added back as
fileOrganizer
on the folders with limited access. If
they were, the entire hierarchy gets deleted. If not, the folders with limited
access move to the shared drive's root folder.


## About expansive access

The introduction of folders with limited access broadens the expansive access
model from shared drives to My Drive. Once the access model is
rolled out, having access to a folder means at least the same level of access to
everything in that folder hierarchy. Folders with limited access are the one
exception that allows restricting access to a specific subfolder in both My
Drive and shared drives. This also means that unless your folder
has limited access, you can no longer remove access that's inherited from the
parent folder. Doing so means Drive API returns an error response. To
define more granular access control within a hierarchy, you can
set limited
access
on the folder.


### Adapt to expansive access

To make it easier for developers to adapt to expansive access, several
improvements were made to the Google Drive API:

- The
permissionDetails[]
field on the
permissions
resource is now
populated for items in My Drive. Previously, the fields were
either unset or replicated from the
teamDrivePermissionDetails
field where
appropriate. Only the
permissionType
and
inherited
fields in
My Drive are populated.
The
permissionDetails[].inherited
field indicates if a permission is
inherited from the item's parent. It lets you detect if certain roles (such
as
reader
) are inherited from the parent, and if a higher role (such as
writer
) is granted on the item directly.
When viewing the permissions for an item, the
permissionDetails[]
field
might contain multiple entries. If present, there's one entry for the
permission directly on the item for that scope, and then entries for the
inherited or member permissions on the item.
The
permissionDetails[]
field on the
permissions
resource is now
populated for items in My Drive. Previously, the fields were
either unset or replicated from the
teamDrivePermissionDetails
field where
appropriate. Only the
permissionType
and
inherited
fields in
My Drive are populated.

The
permissionDetails[].inherited
field indicates if a permission is
inherited from the item's parent. It lets you detect if certain roles (such
as
reader
) are inherited from the parent, and if a higher role (such as
writer
) is granted on the item directly.

When viewing the permissions for an item, the
permissionDetails[]
field
might contain multiple entries. If present, there's one entry for the
permission directly on the item for that scope, and then entries for the
inherited or member permissions on the item.

- Developers can opt in to expansive access API behavior in My
Drive ahead of any future mandatory enforcement. You can set
the
enforceExpansiveAccess
request parameter to
true
so that future
changes to expansive access don't affect your app.
Opting in now means the API operates the same for items in My
Drive as it already does for items in shared drives. For
example, any attempt to restrict access below the inherited role fails when
calling
permissions.update()
.
Similarly, a call to
permissions.delete()
fails if the permission is inherited.
Developers can opt in to expansive access API behavior in My
Drive ahead of any future mandatory enforcement. You can set
the
enforceExpansiveAccess
request parameter to
true
so that future
changes to expansive access don't affect your app.

Opting in now means the API operates the same for items in My
Drive as it already does for items in shared drives. For
example, any attempt to restrict access below the inherited role fails when
calling
permissions.update()
.
Similarly, a call to
permissions.delete()
fails if the permission is inherited.


### Detect and prevent restricted access

Your app might be creating restricted access (where a user has access to the
parent My Drive folder but not to a file within that folder) on
your My Drive folders when using the
permissions.update()
or
permissions.delete()
methods.

When using these methods, you can review the fields on the
permissions
resource to see where a request might create restricted access and avoid sending
such requests. To detect this situation, use the
enforceExpansiveAccess
field on your request.

Additionally, if your app has already created restricted access on your folders,
you can take the following steps:

- Traverse the folder hierarchy to remove the restricted access. In its place,
you should
set limited folder access
.
Traverse the folder hierarchy to remove the restricted access. In its place,
you should
set limited folder access
.

- If the item you're trying to unshare is a file, you can create an
intermediate folder, set limited access on it, and move the file inside the
new folder.
If the item you're trying to unshare is a file, you can create an
intermediate folder, set limited access on it, and move the file inside the
new folder.

- If you don't want to use limited access folders but must remove some access,
you can move the file to a private folder (such as the My
Drive root folder). You can then
create a
shortcut
to the item's original location so
users can still use it.
If you don't want to use limited access folders but must remove some access,
you can move the file to a private folder (such as the My
Drive root folder). You can then
create a
shortcut
to the item's original location so
users can still use it.


## Related topics

- Share files, folders, and drives
- How file access works in shared drives
- Learn about folders with limited access
Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2026-04-20 UTC.


---

# Usage limits Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/guides/limits

- Home
- Google Workspace
- Google Drive
- Reference
As the Google Drive API is a shared service, we apply quotas and limitations to
make sure it's used fairly by all users and to protect the overall performance
of the Google Workspace system.

Limits are defined in terms of
quota units
, an abstract
unit of measurement representing Google Drive resource usage.


## Drive API quotas

Three types of quotas are enforced:

- Per minute per project:
This is the number of quota units your
Google Cloud project can use in one minute.
Per minute per project:
This is the number of quota units your
Google Cloud project can use in one minute.

- Per minute per user per project:
This is the number of quota units any
one particular user can use in your Cloud project. This limit aims
at helping you ensure a fair distribution of usage among your users.
Per minute per user per project:
This is the number of quota units any
one particular user can use in your Cloud project. This limit aims
at helping you ensure a fair distribution of usage among your users.

- Per day per project
: This defines the maximum number of bytes your
Google Cloud project can egress within a 24-hour period before charges apply.
Per day per project
: This defines the maximum number of bytes your
Google Cloud project can egress within a 24-hour period before charges apply.

The following table details these limits:


| Usage limit type | Limit |
| --- | --- |
| Per minute per project | 1,000,000 quota units |
| Per minute per user per project | 325,000 quota units |
| Per day per project | 1 TB |

If you exceed a quota, you'll receive a
403: User rate limit
exceeded
HTTP
status code response. Additional rate limit checks on the Drive
backend might also generate a
429: Rate limit
exceeded
response. If this happens, you should use an
exponential backoff
algorithm
and try again later.


## Daily billing threshold

This
per day per project
limit defines the maximum number of quota units
your Google Cloud project can use within a 24-hour period before charges apply.

Usage under this threshold doesn't incur extra charges and your Google Cloud
account isn't billed. Full billing details will be shared later in 2026 with at
least 90 days' notice before any changes take effect.

You cannot request an increase on this daily threshold limit.

The following table details the limit:


| Threshold limit type | Limit |
| --- | --- |
| Per day per project | 400,000,000 quota units |

For more information, see
Google Workspace standardized model for agent tools
and APIs
.


## Per-method quota usage

The number of quota units consumed per request varies depending on the method
called. The following table outlines the per-method quota unit usage:


| Action | Quota units |
| --- | --- |
| Read items, such as
files.get | 5 |
| List items, such as
files.list | 100 |
| Download items, such as
files.download | 200 |
| Edit items, such as
files.update | 50 |
| Other actions, such as
files.generateIds | 5 |


## Additional constraints

The following constraints are enforced when working with Drive API:

- Google Workspace users can only upload 750 GB per day between My
Drive and all shared drives; this limit also applies to
copies.
Google Workspace users can only upload 750 GB per day between My
Drive and all shared drives; this limit also applies to
copies.

- Users who reach the 750 GB limit or upload a file larger than 750 GB can't
upload or copy additional files until 24 hours have passed.
Users who reach the 750 GB limit or upload a file larger than 750 GB can't
upload or copy additional files until 24 hours have passed.

- The maximum file size that users can upload is 5 TB; only the first file
that breaks the limit completes uploading. The maximum file size that users
can copy is 750 GB.
The maximum file size that users can upload is 5 TB; only the first file
that breaks the limit completes uploading. The maximum file size that users
can copy is 750 GB.

- Notifications
delivered to the address
specified when opening a notification channel don't count against your quota
limits. However, calls to the
changes.watch
,
channels.stop
, and
files.watch
methods do
count against your quota.
Notifications
delivered to the address
specified when opening a notification channel don't count against your quota
limits. However, calls to the
changes.watch
,
channels.stop
, and
files.watch
methods do
count against your quota.

- Provided you stay within the per-minute quotas, there's no limit to the
number of requests you can make per day.
Provided you stay within the per-minute quotas, there's no limit to the
number of requests you can make per day.

- Depending on your type of Google Workspace account, there are additional
Drive storage limits
.
Depending on your type of Google Workspace account, there are additional
Drive storage limits
.


## Resolve time-based quota errors

For all time-based errors (maximum of N requests per X minutes), we recommend
 your code catches the exception and uses a
truncated exponential backoff
to make sure your
 devices don't generate excessive load.

Exponential backoff is a standard error handling strategy for network applications. An 
 exponential backoff algorithm retries requests using exponentially increasing wait times 
 between requests, up to a maximum backoff time. If requests are still unsuccessful, it's 
 important that the delays between requests increase over time until the request is successful.


### Example algorithm

An exponential backoff algorithm retries requests exponentially, increasing the wait time 
 between retries up to a maximum backoff time. For example:

- Make a request to Google Drive API.
- If the request fails, wait 1 +
random_number_milliseconds
and retry
 the request.
- If the request fails, wait 2 +
random_number_milliseconds
and retry
 the request.
- If the request fails, wait 4 +
random_number_milliseconds
and retry
 the request.
- And so on, up to a
maximum_backoff
time.
- Continue waiting and retrying up to some maximum number of retries, but don't increase the wait
 period between retries.
where:

- The wait time is
min(((2^n)+random_number_milliseconds), maximum_backoff)
,
 with
n
incremented by 1 for each iteration (request).
- random_number_milliseconds
is a random number of milliseconds less than or
 equal to 1,000. This helps to avoid cases in which many clients are synchronized by
 some situation and all retry at once, sending requests in synchronized
 waves. The value of
random_number_milliseconds
is recalculated after each
 retry request.
- maximum_backoff
is typically 32 or 64 seconds. The appropriate value
 depends on the use case.
The client can continue retrying after it has reached the
maximum_backoff
time.
 Retries after this point don't need to continue increasing backoff time. For
 example, if a client uses a
maximum_backoff
time of 64 seconds, then after reaching 
 this value, the client can retry every 64 seconds. At some point,
 clients should be prevented from retrying indefinitely.

The wait time between retries and the number of retries depend on your use case
 and network conditions.


## Pricing

All standard use of the Google Drive API is available at no additional cost. Exceeding the quota
 request limits is planned to incur charges to your Google Cloud billing account later in 2026.
 For more information, see
Google Workspace standardized model
 for agent tools and APIs
.


## Request a quota increase

Depending on your project's resource usage, you might want to request a quota
adjustment. API calls by a service account are considered to be using a
single account. Applying for an adjusted quota doesn't guarantee approval. Quota adjustment
requests that would significantly increase the quota value can take longer to be approved.

Not all projects have the same quotas. As you increasingly use Google Cloud over
time, your quota values might need to increase. If you expect a notable upcoming
increase in usage, you can proactively
request quota adjustments
from the
Quotas & System Limits
page in the Google Cloud console.

To learn more, see the following resources:

- About quota adjustments
- View your quota usage and limits
- Request a higher quota limit

## Related topics

- Improve performance
- File and folder limits
- File and folder limits in shared drives
Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2026-05-01 UTC.


---

# List labels on a file Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/guides/list-labels

- Home
- Google Workspace
- Google Drive
- Guides
Your organization can have multiple labels, with labels having any number of
fields. This page describes how to list all labels on a single Google Drive
file.

To list the file labels, use the
files.listLabels
method. The
request body must be empty. The method also takes the optional query parameter
maxResults
to set the maximum number of labels to return per page. If not set,
100 results are returned.

If successful, the
response
body
contains the
list of labels applied to a file. These exist within an
items
object of type
Label
.


## Example

The following code sample shows how to use the label's
fileId
to retrieve the
correct labels.


### Java


```
List<Label>
labelList
=
labelsDriveClient
.
files
().
listLabels
(
"
FILE_ID
"
).
execute
().
getItems
();
```


### Python


```
label_list_response
=
drive_service
.
files
()
.
listLabels
(
fileId
=
"
FILE_ID
"
)
.
execute
();
```


### Node.js


```
/**
* Lists all the labels on a Drive file
* @return{obj} a list of Labels
**/
async
function
listLabels
()
{
// Get credentials and build service
// TODO (developer) - Use appropriate auth mechanism for your app
const
{
GoogleAuth
}
=
require
(
'google-auth-library'
);
const
{
google
}
=
require
(
'googleapis'
);
const
auth
=
new
GoogleAuth
({
scopes
:
'https://www.googleapis.com/auth/drive'
});
const
service
=
google
.
drive
({
version
:
'v3'
,
auth
});
try
{
const
labelListResponse
=
await
service
.
files
.
listLabels
({
fileId
:
'
FILE_ID
'
,
});
return
labelListResponse
;
}
catch
(
err
)
{
// TODO (developer) - Handle error
throw
err
;
}
}
```

Replace
FILE_ID
with the
fileId
of the file for which you
want the list of labels.

Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2026-04-20 UTC.


---

# Manage long-running operations Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/guides/long-running-operations

- Home
- Google Workspace
- Google Drive
- Guides
A long-running operation (LRO) is an API method that takes a longer time to
complete than is appropriate for an API response. Typically, you don't want to
hold the calling thread open while the task runs as it offers a poor user
experience. Instead, it's better to return some type of promise to the user and
allow them to check back later.

The Google Drive API returns a LRO every time you call the
download
method on the
files
resource to download the content of a file
either through the Drive API or its
client
libraries
.

The method returns an
operations
resource to
the client. You can use the
operations
resource to asynchronously retrieve the
status of the API method by polling the operation through the
get
method. LROs in Drive API adhere to
the
Google Cloud LRO design
pattern
.

For more information, see
Long-running operations
.


## Process overview

The following diagram shows the high-level steps of how the
file.download
method works.

- Call
files.download
: When your app calls the
download
method, it
launches the Drive API download request for the file. For more
information, see
Download files
.
Call
files.download
: When your app calls the
download
method, it
launches the Drive API download request for the file. For more
information, see
Download files
.

- Request permissions
: The request sends authentication credentials to the
Drive API. If your app requires calling Drive API using
a user's authentication that hasn't yet been granted, it prompts the user to
sign in. Your app also asks for access with
scopes
that you specify
when setting up authentication.
Request permissions
: The request sends authentication credentials to the
Drive API. If your app requires calling Drive API using
a user's authentication that hasn't yet been granted, it prompts the user to
sign in. Your app also asks for access with
scopes
that you specify
when setting up authentication.

- Start download
: A Drive API request is made to start the file
download. The request could be made to Google Vids or some other
Google Workspace content.
Start download
: A Drive API request is made to start the file
download. The request could be made to Google Vids or some other
Google Workspace content.

- Start LRO
: A long-running operation begins and it manages the download
process.
Start LRO
: A long-running operation begins and it manages the download
process.

- Return pending operation
: The Drive API returns a pending
operation containing information about the user making the request and
several file metadata fields.
Return pending operation
: The Drive API returns a pending
operation containing information about the user making the request and
several file metadata fields.

- Initial pending state
: Your app receives the pending operation along
with an initial pending state of
done=null
. This denotes the file isn't
ready for download yet and that the operation status is pending.
Initial pending state
: Your app receives the pending operation along
with an initial pending state of
done=null
. This denotes the file isn't
ready for download yet and that the operation status is pending.

- Call
operations.get
and verify result
: Your app calls the
get
at the
recommended intervals to poll the operation result and get the latest state
of a long-running operation. If the pending state of
done=false
is
returned, your app must keep polling until the operation returns the
completed state (
done=true
). For large files, expect to poll multiple
times. For more information, see
Get the details about a long-running
operation
.
Call
operations.get
and verify result
: Your app calls the
get
at the
recommended intervals to poll the operation result and get the latest state
of a long-running operation. If the pending state of
done=false
is
returned, your app must keep polling until the operation returns the
completed state (
done=true
). For large files, expect to poll multiple
times. For more information, see
Get the details about a long-running
operation
.

- Check pending state
: If the pending state of
done=true
is returned
from the LRO, this denotes the file is ready for download and that the
operation status is complete.
Check pending state
: If the pending state of
done=true
is returned
from the LRO, this denotes the file is ready for download and that the
operation status is complete.

- Return completed operation with download URI
: Once the LRO is done, the
Drive API returns the download URI and the file is now available
to the user.
Return completed operation with download URI
: Once the LRO is done, the
Drive API returns the download URI and the file is now available
to the user.


## Download files

To download content under a long-running operation, use the
download
method on the
files
resource. The method takes the parameters of
file_id
,
mime_type
, and
revision_id
:

- Required. The
file_id
path parameter is the ID of the file to download.
Required. The
file_id
path parameter is the ID of the file to download.

- Optional. The
mime_type
query parameter denotes the MIME type the method
should use. It's only available when downloading non-blob media content
(such as Google Workspace documents). For a complete list of supported
MIME types, see
Export MIME types for Google Workspace documents
.
If the MIME type isn't set, the Google Workspace document is downloaded
with a default MIME type. For more information, see
Default MIME
types
.
Optional. The
mime_type
query parameter denotes the MIME type the method
should use. It's only available when downloading non-blob media content
(such as Google Workspace documents). For a complete list of supported
MIME types, see
Export MIME types for Google Workspace documents
.

If the MIME type isn't set, the Google Workspace document is downloaded
with a default MIME type. For more information, see
Default MIME
types
.

- Optional. The
revision_id
query parameter is the revision ID of the file
to download. It's only available when downloading blob files, Google Docs,
and Google Sheets. Returns error code
INVALID_ARGUMENT
when downloading
a specific revision on unsupported files.
Optional. The
revision_id
query parameter is the revision ID of the file
to download. It's only available when downloading blob files, Google Docs,
and Google Sheets. Returns error code
INVALID_ARGUMENT
when downloading
a specific revision on unsupported files.

The
download
method is the only way to download Vids
files in MP4 format and is typically best suited to downloading most video
files. If you attempt to export Google Vids files, you receive a
fileNotExportable
error.

Download links generated for Google Docs or Sheets initially
return a redirect. Click the new link to download the file.

A request to the
download
method that begins the LRO, and the request to fetch
the final download URI, should both use resource keys. For more information, see
Access link-shared Drive files using resource keys
.

The request protocol is shown here.


```
POST
https
:
//
www
.
googleapis
.
com
/
drive
/
v3
/
files
/
{
FILE_ID
}
/
download
```

Replace
FILE_ID
with the
fileId
of the file that you want to
download.


### Default MIME types

If a MIME type isn't set when downloading non-blob content, the following
default MIME types are assigned:


| Document Type | Format | MIME type | File Extension |
| --- | --- | --- | --- |
| Google Apps Script | JSON | application/vnd.google-apps.script+json | .json |
| Google Docs | Microsoft Word | application/vnd.openxmlformats-officedocument.wordprocessingml.document | .docx |
| Google Drawings | PNG | image/png | .png |
| Google Forms | ZIP | application/zip | .zip |
| Google Sheets | Microsoft Excel | application/vnd.openxmlformats-officedocument.spreadsheetml.sheet | .xlsx |
| Google Sites | Raw Text | text/raw | .txt |
| Google Slides | Microsoft PowerPoint | application/vnd.openxmlformats-officedocument.presentationml.presentation | .pptx |
| Google Vids | MP4 | video/mp4 | .mp4 |
| Jamboard | PDF | application/pdf | .pdf |


### Download response

When calling the
download
method, the
response body
consists of a
resource representing a long-running operation. The method typically returns a
link to download the file contents.


```
{
"done"
:
true
,
"metadata"
:
{
"@type"
:
"type.googleapis.com/google.apps.drive.v3.DownloadFileMetadata"
,
"resourceKey"
:
"
RESOURCE_KEY
"
},
"name"
:
"
NAME
"
,
"response"
:
{
"@type"
:
"type.googleapis.com/google.apps.drive.v3.DownloadFileResponse"
,
"downloadUri"
:
"
DOWNLOAD_URI
"
,
"partialDownloadAllowed"
:
false
}
}
```

This output includes the following values:

- RESOURCE_KEY
: A resource key helps protect your file from
unintended access. For more information, see
Access link-shared
Drive files using resource
keys
.
RESOURCE_KEY
: A resource key helps protect your file from
unintended access. For more information, see
Access link-shared
Drive files using resource
keys
.

- NAME
: The server-assigned name.
NAME
: The server-assigned name.

- DOWNLOAD_URI
: The final download URI for the file.
DOWNLOAD_URI
: The final download URI for the file.

Note that the
partialDownloadAllowed
field denotes if a
partial download
is permitted and is
true
when downloading blob file content.


## Get the details about a long-running operation

Long-running operations are method calls that might take a substantial amount of
time to complete. Typically, newly created download operations are initially
returned in a pending state (
done=null
), especially for Vids
files.

You can use the
operations
resource that
Drive API provides to check the status of the processing LRO by
including the unique server-assigned name.

The
get
method gets the latest state of a
long-running operation asynchronously. Clients can use this method to poll the
operation result at intervals as recommended by the API service.


### Poll a long-running operation

To poll an available LRO, repeatedly call the
get
method until the operation finishes.
Use an
exponential backoff
between each
poll request, such as 10 seconds.

An LRO remains available for a minimum of 12 hours but in some cases can persist
longer. This duration is subject to change and can be different between file
types. Once the resource expires a new
download
method request is necessary.

Any requests to
get
should use resource keys. For more information, see
Access link-shared Drive files using resource keys
.

The request protocols are shown here.


### Method call


```
operations.get(name='
NAME
');
```

Replace
NAME
with the operation's server-assigned name as
shown in the response to the
download
method request.


### curl


```bash
curl -i -H \
'Authorization: Bearer $(gcloud auth print-access-token)" \
'https://googleapis.com/drive/v3/operations/
NAME
?alt=json'
```

The command uses the path
/drive/v3/operations/
NAME
.

Note that the
name
is only returned in the response to a
download
request.
There's no other way to retrieve it as Drive API doesn't support the
list
method. If the
name
value is lost, you must generate a new response by
calling the
download
method request again.

The response from a
get
request consists of a resource representing a
long-running operation. For more information, see
Download
response
.

When the response contains a completed state (
done=true
), the long-running
operation has finished.


## Download a revision

You can use the value of the
headRevisionId
field
from the
files
resource to download the latest
revision. This fetches the revision that corresponds to the metadata of the file
you previously retrieved. To download the data for all previous revisions of the
file that are still stored in the cloud, you can call the
list
method on the
revisions
resource with the
fileId
parameter. This returns
all the
revisionIds
in the file.

To download the revision content of blob files, you must call the
get
method on the
revisions
resource with the ID of the file to
download, the ID of the revision, and the
alt
system
parameter
.
The
alt=media
parameter tells the server that a content download is being
requested as an alternative response format.

The
alt
system parameter is available across all Google REST APIs. If you use
a client library for the Drive API, you don't need to explicitly set
this parameter.

Revisions for Google Docs, Sheets, Slides, and
Vids can't be downloaded using the
get
method with the
alt=media
parameter. Otherwise, it generates a
fileNotDownloadable
error.


```bash
GET https://www.googleapis.com/drive/v3/files/{
FILE_ID
}/revisions/{
REVISION_ID
}?alt=media
```

Replace the following:

- FILE_ID
: The
fileId
of the file that you want to
download.
- REVISION_ID
: The
revisionId
of the revision that you want
to download.
Google Docs, Drawings, and Slides revisions
auto-increment the revision numbers. However, the series of numbers might have
gaps if revisions are deleted, so you shouldn't rely on sequential numbers to
retrieve revisions.


## Troubleshoot LROs

When a LRO fails, its response includes a
canonical Google Cloud error
code
.

The following table displays each error code, the mapped HTTP status code, a
description, and a recommendation for how to handle the error code. For many
errors, the recommended action is to try the request again using
exponential
backoff
.

You can read more about this error model and how to work with it in the
API
Design Guide
.


| Code | Enum | HTTP status code | Description | Recommended action |
| --- | --- | --- | --- | --- |
| 1 | CANCELLED | 499 Client Closed Request | The operation was canceled, typically by the caller. | Re-run the operation. |
| 2 | UNKNOWN | 500 Internal Server Error | This error might be returned when a
Status
value received from another address space belongs to an error space that isn't known in this address space. If the API error doesn't return enough information, the error might be converted to this error. | Retry with exponential backoff. |
| 3 | INVALID_ARGUMENT | 400 Bad Request | The client specified an invalid argument. This error differs from
FAILED_PRECONDITION
.
INVALID_ARGUMENT
indicates arguments that are problematic regardless of the state of the system, such as a malformed filename. | Don't retry without fixing the problem. |
| 4 | DEADLINE_EXCEEDED | 504 Gateway Timeout | The deadline expired before the operation could complete. For operations that change the state of the system, this error might be returned even if the operation has completed successfully. For example, a successful response from a server could have been delayed long enough for the deadline to expire. | Retry with exponential backoff. |
| 5 | NOT_FOUND | 404 Not Found | Some requested entity, such as a FHIR resource, wasn't found. | Don't retry without fixing the problem. |
| 6 | ALREADY_EXISTS | 409 Conflict | The entity that a client attempted to create, such as a DICOM instance, already exists. | Don't retry without fixing the problem. |
| 7 | PERMISSION_DENIED | 403 Forbidden | The caller doesn't have permission to execute the specified operation. This error code doesn't imply the request is valid, the requested entity exists, or it satisfies other preconditions. | Don't retry without fixing the problem. |
| 8 | RESOURCE_EXHAUSTED | 429 Too Many Requests | Some resource has been exhausted, such as a per-project quota. | Retry with exponential backoff. Quota might become available over time. |
| 9 | FAILED_PRECONDITION | 400 Bad Request | The operation was rejected because the system isn't in a state required for the operation's execution. For example, the directory to be deleted is non-empty, or an
rmdir
operation is applied to a non-directory. | Don't retry without fixing the problem. |
| 10 | ABORTED | 409 Conflict | The operation was aborted, typically due to a concurrency issue such as a sequencer check failure or transaction abort. | Retry with exponential backoff. |
| 11 | OUT_OF_RANGE | 400 Bad Request | The operation was attempted past the valid range, such as seeking or reading past end-of-file. Unlike
INVALID_ARGUMENT
, this error indicates a problem that may be fixed if the system state changes. | Don't retry without fixing the problem. |
| 12 | UNIMPLEMENTED | 501 Not Implemented | The operation isn't implemented or isn't supported/enabled in the Drive API. | Don't retry. |
| 13 | INTERNAL | 500 Internal Server Error | Internal errors. This indicates that an unexpected error was encountered in processing on the underlying system. | Retry with exponential backoff. |
| 14 | UNAVAILABLE | 503 Service Unavailable | The Drive API is unavailable. This is most likely a transient condition, which can be corrected by retrying with exponential backoff. Note that it's not always safe to retry non-idempotent operations. | Retry with exponential backoff. |
| 15 | DATA_LOSS | 500 Internal Server Error | Unrecoverable data loss or corruption. | Contact your system administrator. The system administrator might want to contact a support representative if data loss or corruption occurred. |
| 16 | UNAUTHENTICATED | 401 Unauthorized | The request doesn't have valid authentication credentials for the operation. | Don't retry without fixing the problem. |


## Related topics

- Download and export files
Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2026-05-07 UTC.


---

# Retrieve changes Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/guides/manage-changes

- Home
- Google Workspace
- Google Drive
- Guides
For Google Drive apps that must track changes to files, the
changes
collection provides an efficient
way to detect all file changes, including those shared with a user. If the file
has changed, the collection provides the current state of each file.


## Get start page token

To request the page token for the current state of the account, use the
changes.getStartPageToken
.
Store and use this token in your initial call to
changes.list
.

To retrieve the current page token:


### Java


```
import
com.google.api.client.googleapis.json.GoogleJsonResponseException
;
import
com.google.api.client.http.HttpRequestInitializer
;
import
com.google.api.client.http.javanet.NetHttpTransport
;
import
com.google.api.client.json.gson.GsonFactory
;
import
com.google.api.services.drive.Drive
;
import
com.google.api.services.drive.DriveScopes
;
import
com.google.api.services.drive.model.StartPageToken
;
import
com.google.auth.http.HttpCredentialsAdapter
;
import
com.google.auth.oauth2.GoogleCredentials
;
import
java.io.IOException
;
import
java.util.Arrays
;
/* Class to demonstrate use-case of Drive's fetch start page token */
public
class
FetchStartPageToken
{
/**
* Retrieve the start page token for the first time.
*
* @return Start page token as String.
* @throws IOException if file is not found
*/
public
static
String
fetchStartPageToken
()
throws
IOException
{
/*Load pre-authorized user credentials from the environment.
TODO(developer) - See https://developers.google.com/identity for
guides on implementing OAuth2 for your application. */
GoogleCredentials
credentials
=
GoogleCredentials
.
getApplicationDefault
()
.
createScoped
(
Arrays
.
asList
(
DriveScopes
.
DRIVE_FILE
));
HttpRequestInitializer
requestInitializer
=
new
HttpCredentialsAdapter
(
credentials
);
// Build a new authorized API client service.
Drive
service
=
new
Drive
.
Builder
(
new
NetHttpTransport
(),
GsonFactory
.
getDefaultInstance
(),
requestInitializer
)
.
setApplicationName
(
"Drive samples"
)
.
build
();
try
{
StartPageToken
response
=
service
.
changes
()
.
getStartPageToken
().
execute
();
System
.
out
.
println
(
"Start token: "
+
response
.
getStartPageToken
());
return
response
.
getStartPageToken
();
}
catch
(
GoogleJsonResponseException
e
)
{
// TODO(developer) - handle error appropriately
System
.
err
.
println
(
"Unable to fetch start page token: "
+
e
.
getDetails
());
throw
e
;
}
}
}
```


### Python


```
import
google.auth
from
googleapiclient.discovery
import
build
from
googleapiclient.errors
import
HttpError
def
fetch_start_page_token
():
"""Retrieve page token for the current state of the account.
Returns & prints : start page token
Load pre-authorized user credentials from the environment.
TODO(developer) - See https://developers.google.com/identity
for guides on implementing OAuth2 for the application.
"""
creds
,
_
=
google
.
auth
.
default
()
try
:
# create drive api client
service
=
build
(
"drive"
,
"v3"
,
credentials
=
creds
)
# pylint: disable=maybe-no-member
response
=
service
.
changes
()
.
getStartPageToken
()
.
execute
()
print
(
f
'Start token:
{
response
.
get
(
"startPageToken"
)
}
'
)
except
HttpError
as
error
:
print
(
f
"An error occurred:
{
error
}
"
)
response
=
None
return
response
.
get
(
"startPageToken"
)
if
__name__
==
"__main__"
:
fetch_start_page_token
()
```


### PHP


```
<
?php
use Google\Client;
use Google\Service\Drive;
# TODO - PHP client currently chokes on fetching start page token
function fetchStartPageToken()
{
try {
$client = new Client();
$client->useApplicationDefaultCredentials();
$client->addScope(Drive::DRIVE);
$driveService = new Drive($client);
$response = $driveService->changes->getStartPageToken();
printf("Start token: %s\n", $response->startPageToken);
return $response->startPageToken;
} catch(Exception $e) {
echo "Error Message: ".$e;
}
}
```


### .NET


```
using
Google.Apis.Auth.OAuth2
;
using
Google.Apis.Drive.v3
;
using
Google.Apis.Services
;
namespace
DriveV3Snippets
{
// Class to demonstrate use-case of Drive's fetch start page token
public
class
FetchStartPageToken
{
/// <summary>
/// Retrieve the starting page token.
/// </summary>
/// <returns>start page token as String, null otherwise.</returns>
public
static
string
DriveFetchStartPageToken
()
{
try
{
/* Load pre-authorized user credentials from the environment.
TODO(developer) - See https://developers.google.com/identity for
guides on implementing OAuth2 for your application. */
GoogleCredential
credential
=
GoogleCredential
.
GetApplicationDefault
()
.
CreateScoped
(
DriveService
.
Scope
.
Drive
);
// Create Drive API service.
var
service
=
new
DriveService
(
new
BaseClientService
.
Initializer
{
HttpClientInitializer
=
credential
,
ApplicationName
=
"Drive API Snippets"
});
var
response
=
service
.
Changes
.
GetStartPageToken
().
Execute
();
// Prints the token value.
Console
.
WriteLine
(
"Start token: "
+
response
.
StartPageTokenValue
);
return
response
.
StartPageTokenValue
;
}
catch
(
Exception
e
)
{
// TODO(developer) - handle error appropriately
if
(
e
is
AggregateException
)
{
Console
.
WriteLine
(
"Credential Not found"
);
}
else
{
throw
;
}
}
return
null
;
}
}
}
```


### Node.js


```
import
{
GoogleAuth
}
from
'google-auth-library'
;
import
{
google
}
from
'googleapis'
;
/**
* Fetches the start page token for the current state of the account.
* @return {Promise<string>} The start page token.
*/
async
function
fetchStartPageToken
()
{
// Authenticate with Google and get an authorized client.
// TODO (developer): Use an appropriate auth mechanism for your app.
const
auth
=
new
GoogleAuth
({
scopes
:
'https://www.googleapis.com/auth/drive.appdata'
,
});
// Create a new Drive API client (v3).
const
service
=
google
.
drive
({
version
:
'v3'
,
auth
});
// Fetch the start page token.
const
res
=
await
service
.
changes
.
getStartPageToken
({});
const
token
=
res
.
data
.
startPageToken
;
console
.
log
(
'start token: '
,
token
);
if
(
!
token
)
{
throw
new
Error
(
'Start page token not found.'
);
}
return
token
;
}
```


## Get changes

To retrieve the list of changes for the currently signed in user, send a
GET
request to the
changes
collection, as detailed in the
changes.list
.

Entries in the
changes
collection are in chronological order (the oldest
changes appear first). The
includeRemoved
and
restrictToMyDrive
query
parameters determine whether the response should include removed or shared
items.


```
import
com.google.api.client.googleapis.json.GoogleJsonResponseException
;
import
com.google.api.client.http.HttpRequestInitializer
;
import
com.google.api.client.http.javanet.NetHttpTransport
;
import
com.google.api.client.json.gson.GsonFactory
;
import
com.google.api.services.drive.Drive
;
import
com.google.api.services.drive.DriveScopes
;
import
com.google.api.services.drive.model.ChangeList
;
import
com.google.auth.http.HttpCredentialsAdapter
;
import
com.google.auth.oauth2.GoogleCredentials
;
import
java.io.IOException
;
import
java.util.Arrays
;
/* Class to demonstrate use-case of Drive's fetch changes in file. */
public
class
FetchChanges
{
/**
* Retrieve the list of changes for the currently authenticated user.
*
* @param savedStartPageToken Last saved start token for this user.
* @return Saved token after last page.
* @throws IOException if file is not found
*/
public
static
String
fetchChanges
(
String
savedStartPageToken
)
throws
IOException
{
/*Load pre-authorized user credentials from the environment.
TODO(developer) - See https://developers.google.com/identity for
guides on implementing OAuth2 for your application.*/
GoogleCredentials
credentials
=
GoogleCredentials
.
getApplicationDefault
()
.
createScoped
(
Arrays
.
asList
(
DriveScopes
.
DRIVE_FILE
));
HttpRequestInitializer
requestInitializer
=
new
HttpCredentialsAdapter
(
credentials
);
// Build a new authorized API client service.
Drive
service
=
new
Drive
.
Builder
(
new
NetHttpTransport
(),
GsonFactory
.
getDefaultInstance
(),
requestInitializer
)
.
setApplicationName
(
"Drive samples"
)
.
build
();
try
{
// Begin with our last saved start token for this user or the
// current token from getStartPageToken()
String
pageToken
=
savedStartPageToken
;
while
(
pageToken
!=
null
)
{
ChangeList
changes
=
service
.
changes
().
list
(
pageToken
)
.
execute
();
for
(
com
.
google
.
api
.
services
.
drive
.
model
.
Change
change
:
changes
.
getChanges
())
{
// Process change
System
.
out
.
println
(
"Change found for file: "
+
change
.
getFileId
());
}
if
(
changes
.
getNewStartPageToken
()
!=
null
)
{
// Last page, save this token for the next polling interval
savedStartPageToken
=
changes
.
getNewStartPageToken
();
}
pageToken
=
changes
.
getNextPageToken
();
}
return
savedStartPageToken
;
}
catch
(
GoogleJsonResponseException
e
)
{
// TODO(developer) - handle error appropriately
System
.
err
.
println
(
"Unable to fetch changes: "
+
e
.
getDetails
());
throw
e
;
}
}
}
```


```
import
google.auth
from
googleapiclient.discovery
import
build
from
googleapiclient.errors
import
HttpError
def
fetch_changes
(
saved_start_page_token
):
"""Retrieve the list of changes for the currently authenticated user.
prints changed file's ID
Args:
saved_start_page_token : StartPageToken for the current state of the
account.
Returns: saved start page token.
Load pre-authorized user credentials from the environment.
TODO(developer) - See https://developers.google.com/identity
for guides on implementing OAuth2 for the application.
"""
creds
,
_
=
google
.
auth
.
default
()
try
:
# create drive api client
service
=
build
(
"drive"
,
"v3"
,
credentials
=
creds
)
# Begin with our last saved start token for this user or the
# current token from getStartPageToken()
page_token
=
saved_start_page_token
# pylint: disable=maybe-no-member
while
page_token
is
not
None
:
response
=
(
service
.
changes
()
.
list
(
pageToken
=
page_token
,
spaces
=
"drive"
)
.
execute
()
)
for
change
in
response
.
get
(
"changes"
):
# Process change
print
(
f
'Change found for file:
{
change
.
get
(
"fileId"
)
}
'
)
if
"newStartPageToken"
in
response
:
# Last page, save this token for the next polling interval
saved_start_page_token
=
response
.
get
(
"newStartPageToken"
)
page_token
=
response
.
get
(
"nextPageToken"
)
except
HttpError
as
error
:
print
(
f
"An error occurred:
{
error
}
"
)
saved_start_page_token
=
None
return
saved_start_page_token
if
__name__
==
"__main__"
:
# saved_start_page_token is the token number
fetch_changes
(
saved_start_page_token
=
209
)
```


```
<
?php
use Google\Client;
use Google\Service\Drive;
# TODO - PHP client currently chokes on fetching start page token
function fetchChanges()
{
try {
$client = new Client();
$client->useApplicationDefaultCredentials();
$client->addScope(Drive::DRIVE);
$driveService = new Drive($client);
# Begin with our last saved start token for this user or the
# current token from getStartPageToken()
$savedStartPageToken = readLine("Enter Start Page Token: ");
$pageToken = $savedStartPageToken;
while ($pageToken != null) {
$response = $driveService->changes->listChanges($pageToken, array(
'spaces' => 'drive'
));
foreach ($response->changes as $change) {
// Process change
printf("Change found for file: %s", $change->fileId);
}
if ($response->newStartPageToken != null) {
// Last page, save this token for the next polling interval
$savedStartPageToken = $response->newStartPageToken;
}
$pageToken = $response->nextPageToken;
}
echo $savedStartPageToken;
} catch(Exception $e) {
echo "Error Message: ".$e;
}
}
require_once 'vendor/autoload.php';
```


```
using
Google.Apis.Auth.OAuth2
;
using
Google.Apis.Drive.v3
;
using
Google.Apis.Services
;
namespace
DriveV3Snippets
{
// Class to demonstrate use-case of Drive's fetch changes in file.
public
class
FetchChanges
{
/// <summary>
/// Retrieve the list of changes for the currently authenticated user.
/// prints changed file's ID
/// </summary>
/// <param name="savedStartPageToken">last saved start token for this user.</param>
/// <returns>saved token for the current state of the account, null otherwise.</returns>
public
static
string
DriveFetchChanges
(
string
savedStartPageToken
)
{
try
{
/* Load pre-authorized user credentials from the environment.
TODO(developer) - See https://developers.google.com/identity for
guides on implementing OAuth2 for your application. */
GoogleCredential
credential
=
GoogleCredential
.
GetApplicationDefault
()
.
CreateScoped
(
DriveService
.
Scope
.
Drive
);
// Create Drive API service.
var
service
=
new
DriveService
(
new
BaseClientService
.
Initializer
{
HttpClientInitializer
=
credential
,
ApplicationName
=
"Drive API Snippets"
});
// Begin with our last saved start token for this user or the
// current token from GetStartPageToken()
string
pageToken
=
savedStartPageToken
;
while
(
pageToken
!=
null
)
{
var
request
=
service
.
Changes
.
List
(
pageToken
);
request
.
Spaces
=
"drive"
;
var
changes
=
request
.
Execute
();
foreach
(
var
change
in
changes
.
Changes
)
{
// Process change
Console
.
WriteLine
(
"Change found for file: "
+
change
.
FileId
);
}
if
(
changes
.
NewStartPageToken
!=
null
)
{
// Last page, save this token for the next polling interval
savedStartPageToken
=
changes
.
NewStartPageToken
;
}
pageToken
=
changes
.
NextPageToken
;
}
return
savedStartPageToken
;
}
catch
(
Exception
e
)
{
// TODO(developer) - handle error appropriately
if
(
e
is
AggregateException
)
{
Console
.
WriteLine
(
"Credential Not found"
);
}
else
{
throw
;
}
}
return
null
;
}
}
}
```


```
import
{
GoogleAuth
}
from
'google-auth-library'
;
import
{
google
}
from
'googleapis'
;
/**
* Fetches the list of changes for the currently authenticated user.
* @param {string} savedStartPageToken The page token obtained from `fetch_start_page_token.js`.
*/
async
function
fetchChanges
(
savedStartPageToken
)
{
// Authenticate with Google and get an authorized client.
// TODO (developer): Use an appropriate auth mechanism for your app.
const
auth
=
new
GoogleAuth
({
scopes
:
'https://www.googleapis.com/auth/drive.readonly'
,
});
// Create a new Drive API client (v3).
const
service
=
google
.
drive
({
version
:
'v3'
,
auth
});
// The page token for the next page of changes.
let
pageToken
=
savedStartPageToken
;
// Loop to fetch all changes, handling pagination.
do
{
const
result
=
await
service
.
changes
.
list
({
pageToken
:
savedStartPageToken
,
fields
:
'*'
,
});
// Process the changes.
(
result
.
data
.
changes
??
[]).
forEach
((
change
)
=
>
{
console
.
log
(
'change found for file: '
,
change
.
fileId
);
});
// Update the page token for the next iteration.
pageToken
=
result
.
data
.
newStartPageToken
??
''
;
}
while
(
pageToken
);
}
```

The
changes
collection in the
response
might contain a
nextPageToken
. If the
nextPageToken
is listed, it can be used to gather the
next page of changes. If it's not listed, the client application should store
the
newStartPageToken
in the response for future use. With the page token
stored, the client application is prepared to query again for future changes.


## Receive notifications

Use the
changes.watch
method to
subscribe to updates in the change log. Notifications don't contain details
about the changes. Instead, they indicate that new changes are available. To
retrieve the actual changes, poll the change feed as described in
Get
changes
.

For more information, see
Notifications for resource changes
.

Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2026-04-23 UTC.


---

# Manage comments and replies Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/guides/manage-comments

- Home
- Google Workspace
- Google Drive
- Guides
Comments
are user-provided feedback on a file, such as a reader of a
word-processing document suggesting how to rephrase a sentence. There are two
types of comments:
anchored comments
and
unanchored comments
. An anchored
comment is associated with a specific location, such as a sentence in a
word-processing document, within a specific version of a document. Conversely,
an unanchored comment is just associated with the document.

Replies
are attached to comments and represent a user's response to the
comment. The Drive API lets your users add comments and replies to
documents created by your app. Collectively, a comment with replies is known as
a
discussion
.


## Use the fields parameter

For all methods (excluding
delete
) on the
comments
resource, you
must
set the
fields
system
parameter
to
specify the fields to return in the response. In most Drive
resource methods this action is only required to return non-default fields, but
it's mandatory for the
comments
resource. If you omit the
fields
parameter,
the method returns an error. For more information, see
Return specific fields
.


## Comment constraints

The following constraints are enforced when working with anchored and unanchored
comments with the Drive API:


| Comment type | File type |
| --- | --- |
| Anchored | Developers can can define their own format for the anchor specification.
The anchor is saved and returned when retrieving the comment, however Google Workspace editor apps treat these comments as un-anchored comments. |
| Unanchored | Supported on Google Workspace documents, which will show them in the "All Comments" view.
Unanchored comments are not shown on PDFs rendered in the Drive file previewer, though they are saved and can be retrieved through the Drive API. |

- Developers can can define their own format for the anchor specification.
- The anchor is saved and returned when retrieving the comment, however Google Workspace editor apps treat these comments as un-anchored comments.
- Supported on Google Workspace documents, which will show them in the "All Comments" view.
- Unanchored comments are not shown on PDFs rendered in the Drive file previewer, though they are saved and can be retrieved through the Drive API.

## Add an anchored comment to the latest revision of a document

When you add a comment, you might want to anchor it to a region in the file. An
anchor
defines a region in a file to which a comment refers. The
comments
resource defines the
anchor
field as a JSON string.

To add an anchored comment:

- (Optional). Call the
list
method on
the
revisions
resource to list every
revisionID
for a document. Only follow this step if you want to anchor a
comment to any revision other than the latest revision. If you want to use
the latest revision, use
head
for the
revisionID
.
(Optional). Call the
list
method on
the
revisions
resource to list every
revisionID
for a document. Only follow this step if you want to anchor a
comment to any revision other than the latest revision. If you want to use
the latest revision, use
head
for the
revisionID
.

- Call the
create
method on the
comments
resource with the
fileID
parameter, a
comments
resource containing the comment, and a JSON anchor
string containing the
revisionID
(
r
) and region (
a
).
Call the
create
method on the
comments
resource with the
fileID
parameter, a
comments
resource containing the comment, and a JSON anchor
string containing the
revisionID
(
r
) and region (
a
).

The following code sample shows how to create an anchored comment:


### Python


```
from
google.oauth2.credentials
import
Credentials
from
googleapiclient.errors
import
HttpError
# --- Configuration ---
# The ID of the file to comment on.
# Example: '1_aBcDeFgHiJkLmNoPqRsTuVwXyZ'
FILE_ID
=
'FILE_ID'
# The text content of the comment.
COMMENT_TEXT
=
'This is an example of an anchored comment.'
# The line number to anchor the comment to.
# Note: Line numbers are based on the revision.
ANCHOR_LINE
=
10
# --- End of user-configuration section ---
SCOPES
=
[
"https://www.googleapis.com/auth/drive"
]
creds
=
Credentials
.
from_authorized_user_file
(
"token.json"
,
SCOPES
)
def
create_anchored_comment
():
"""
Create an anchored comment on a specific line in a Google Doc.
Returns:
The created comment object or None if an error occurred.
"""
try
:
# Build the Drive API service
service
=
build
(
"drive"
,
"v3"
,
credentials
=
creds
)
# Define the anchor region for the comment.
# For Google Docs, the region is typically defined by 'line' and 'revision'.
# Other file types might use different region classifiers.
anchor
=
{
'region'
:
{
'kind'
:
'drive#commentRegion'
,
'line'
:
ANCHOR_LINE
,
'rev'
:
'head'
}
}
# The comment body.
comment_body
=
{
'content'
:
COMMENT_TEXT
,
'anchor'
:
anchor
}
# Create the comment request.
comment
=
(
service
.
comments
()
.
create
(
fileId
=
FILE_ID
,
fields
=
"*"
,
body
=
comment_body
)
.
execute
()
)
print
(
f
"Comment ID:
{
comment
.
get
(
'id'
)
}
"
)
return
comment
except
HttpError
as
error
:
print
(
f
"An error occurred:
{
error
}
"
)
return
None
create_anchored_comment
()
```

The Drive API returns an instance of the
comments
resource object
which includes the
anchor
string.


## Add an unanchored comment

To add an unanchored comment, call the
create
method with the
fileId
parameter and a
comments
resource containing the comment.

The comment is inserted as plain text, but the response body provides an
htmlContent
field
containing content formatted for display.

The following code sample shows how to create an unanchored comment:


```
from
google.oauth2.credentials
import
Credentials
from
googleapiclient.errors
import
HttpError
# --- Configuration ---
# The ID of the file to comment on.
# Example: '1_aBcDeFgHiJkLmNoPqRsTuVwXyZ'
FILE_ID
=
'FILE_ID'
# The text content of the comment.
COMMENT_TEXT
=
'This is an example of an unanchored comment.'
# --- End of user-configuration section ---
SCOPES
=
[
"https://www.googleapis.com/auth/drive"
]
creds
=
Credentials
.
from_authorized_user_file
(
"token.json"
,
SCOPES
)
def
create_unanchored_comment
():
"""
Create an unanchored comment on a specific line in a Google Doc.
Returns:
The created comment object or None if an error occurred.
"""
try
:
# Build the Drive API service
service
=
build
(
"drive"
,
"v3"
,
credentials
=
creds
)
# The comment body. For an unanchored comment,
# omit the 'anchor' property.
comment_body
=
{
'content'
:
COMMENT_TEXT
}
# Create the comment request.
comment
=
(
service
.
comments
()
.
create
(
fileId
=
FILE_ID
,
fields
=
"*"
,
body
=
comment_body
)
.
execute
()
)
print
(
f
"Comment ID:
{
comment
.
get
(
'id'
)
}
"
)
return
comment
except
HttpError
as
error
:
print
(
f
"An error occurred:
{
error
}
"
)
return
None
create_unanchored_comment
()
```


## Add a reply to a comment

To add a reply to a comment, use the
create
method on the
replies
resource with the
fileId
and
commentId
parameters. The request body uses the
content
field to add the
reply.

The reply is inserted as plain text, but the response body provides an
htmlContent
field containing content formatted for display.

The method returns the fields listed in the
fields
field.

Request

In this example, we provide the
fileId
and
commentId
path parameters and multiple fields.


```bash
POST https://www.googleapis.com/drive/v3/files/
FILE_ID
/comments/
COMMENT_ID
/replies?fields=id,comment
```

Request body


```
{
  "content": "This is a reply to a comment."
}
```


### Resolve a comment

A comment can only be resolved by posting a reply to a comment.

To resolve a comment, use the
create
method on the
replies
resource with the
fileId
and
commentId
parameters.

The request body uses the
action
field to resolve
the comment. You can also set the
content
field to add a reply that closes the
comment.

When a comment is resolved, Drive marks the
comments
resource
as
resolved: true
. Unlike
deleted comments
, resolved
comments can include the
htmlContent
or
content
fields.

When your app resolves a comment, your UI should indicate that the comment has
been addressed. For example, your app might:

- Disallow further replies and dim all previous replies plus the original
comment.
- Hide resolved comments.

```
{
  "action": "resolve",
  "content": "This comment has been resolved."
}
```


## Get a comment

To get a comment on a file, use the
get
method on the
comments
resource with the
fileId
and
commentId
parameters. If you don't know the comment ID, you can
list all comments
using the
list
method.

The method returns an instance of a
comments
resource.

To include deleted comments in the results, set the
includedDeleted
query
parameter to
true
.


```bash
GET https://www.googleapis.com/drive/v3/files/
FILE_ID
/comments/
COMMENT_ID
?fields=id,comment,modifiedTime,resolved
```


## List comments

To list comments on a file, use the
list
method on the
comments
resource with the
fileId
parameter. The method returns a list of comments.

Pass the following query parameters to customize pagination of, or filter,
comments:

- includeDeleted
: Set to
true
to include deleted comments. Deleted
comments don't include the
htmlContent
or
content
fields.
includeDeleted
: Set to
true
to include deleted comments. Deleted
comments don't include the
htmlContent
or
content
fields.

- pageSize
: The maximum number of comments to return per page.
pageSize
: The maximum number of comments to return per page.

- pageToken
: A page token, received from a previous list call. Provide this
token to retrieve the subsequent page.
pageToken
: A page token, received from a previous list call. Provide this
token to retrieve the subsequent page.

- startModifiedTime
: The minimum value of the
modifiedTime
field for the
result comments.
startModifiedTime
: The minimum value of the
modifiedTime
field for the
result comments.

In this example, we provide the
fileId
path parameter, the
includeDeleted
query parameter, and multiple fields.


```bash
GET https://www.googleapis.com/drive/v3/files/
FILE_ID
/comments?includeDeleted=true&fields=(id,comment,kind,modifiedTime,resolved)
```


## Update a comment

To update a comment on a file, use the
update
method on the
comments
resource with the
fileId
and
commentId
parameters. The request body uses the
content
field to update the comment.

The boolean
resolved
field on the
comments
resource is read-only. A comment can only be resolved by
posting a reply to a comment. For more information, see
Resolve a
comment
.

The method returns the fields listed in the
fields
query parameter.


```
PATCH https://www.googleapis.com/drive/v3/files/
FILE_ID
/comments/
COMMENT_ID
?fields=id,comment
```


```
{
  "content": "This comment is now updated."
}
```


## Delete a comment

To delete a comment on a file, use the
delete
method on the
comments
resource with the
fileId
and
commentId
parameters.

When a comment is deleted, Drive marks the comment resource as
deleted: true
. Deleted comments don't include the
htmlContent
or
content
fields.

In this example, we provide the
fileId
and
commentId
path parameters.


```
DELETE https://www.googleapis.com/drive/v3/files/
FILE_ID
/comments/
COMMENT_ID
```


## Related topics

- Files and folders overview
- Manage file revisions
Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2026-04-20 UTC.


---

# Download and export files Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/guides/manage-downloads

- Home
- Google Workspace
- Google Drive
- Guides
The Google Drive API supports several types of download and export actions, as
listed in the following table:


| Download actions | Blob file content using the
files.get
method with the
alt=media
parameter.
Blob file content at an earlier version using the
revisions.get
method with the
alt=media
parameter.
Blob file content in a browser using the
webContentLink
field.
Blob file content using the
files.download
method using long-running operations. This is the only way to download Google Vids files. | Blob file content using the
files.get
method with the
alt=media
parameter. | Blob file content at an earlier version using the
revisions.get
method with the
alt=media
parameter. | Blob file content in a browser using the
webContentLink
field. | Blob file content using the
files.download
method using long-running operations. This is the only way to download Google Vids files. |
| --- | --- | --- | --- | --- | --- |
| Blob file content using the
files.get
method with the
alt=media
parameter. |  |  |  |  |  |
| Blob file content at an earlier version using the
revisions.get
method with the
alt=media
parameter. |  |  |  |  |  |
| Blob file content in a browser using the
webContentLink
field. |  |  |  |  |  |
| Blob file content using the
files.download
method using long-running operations. This is the only way to download Google Vids files. |  |  |  |  |  |
| Export actions | Google Workspace document content in a format that your app can handle, using the
files.export
method.
Google Workspace document content in a browser using the
exportLinks
field.
Google Workspace document content at an earlier version in a browser using the
exportLinks
field.
Google Workspace document content using the
files.download
method using long-running operations. | Google Workspace document content in a format that your app can handle, using the
files.export
method. | Google Workspace document content in a browser using the
exportLinks
field. | Google Workspace document content at an earlier version in a browser using the
exportLinks
field. | Google Workspace document content using the
files.download
method using long-running operations. |
| Google Workspace document content in a format that your app can handle, using the
files.export
method. |  |  |  |  |  |
| Google Workspace document content in a browser using the
exportLinks
field. |  |  |  |  |  |
| Google Workspace document content at an earlier version in a browser using the
exportLinks
field. |  |  |  |  |  |
| Google Workspace document content using the
files.download
method using long-running operations. |  |  |  |  |  |


| Blob file content using the
files.get
method with the
alt=media
parameter. |
| --- |
| Blob file content at an earlier version using the
revisions.get
method with the
alt=media
parameter. |
| Blob file content in a browser using the
webContentLink
field. |
| Blob file content using the
files.download
method using long-running operations. This is the only way to download Google Vids files. |


| Google Workspace document content in a format that your app can handle, using the
files.export
method. |
| --- |
| Google Workspace document content in a browser using the
exportLinks
field. |
| Google Workspace document content at an earlier version in a browser using the
exportLinks
field. |
| Google Workspace document content using the
files.download
method using long-running operations. |

Before you download or export file content, verify that users can download the
file using the
capabilities.canDownload
field on the
files
resource.

For descriptions of the file types mentioned here, including blob and
Google Workspace files, see
File types
.

The rest of this document provides detailed instructions for performing these
types of download and export actions.


## Download blob file content

To download a blob file stored on Drive, use the
files.get
method with the ID of the file to download and the
alt
system
parameter
.
The
alt=media
parameter tells the server that a download of content is being
requested as an alternative response format.

The
alt
system parameter is available across all Google REST APIs. If you use
a Drive API client library, you don't need to explicitly set this
parameter as the client library method adds the
alt=media
parameter to the
underlying HTTP request.

The following code samples show how to use the
files.get
method to download a
file:


### Apps Script


```
/**
* Downloads a file from Drive.
* @param {string} fileId The ID of the file to download.
* @return {Blob} The file content as a Blob.
*/
function
downloadFile
(
fileId
)
{
var
url
=
'https://www.googleapis.com/drive/v3/files/'
+
fileId
+
'?alt=media'
;
var
response
=
UrlFetchApp
.
fetch
(
url
,
{
headers
:
{
'Authorization'
:
'Bearer '
+
ScriptApp
.
getOAuthToken
()
}
});
return
response
.
getBlob
();
}
```


### Java


```
import
com.google.api.client.googleapis.json.GoogleJsonResponseException
;
import
com.google.api.client.http.HttpRequestInitializer
;
import
com.google.api.client.http.javanet.NetHttpTransport
;
import
com.google.api.client.json.gson.GsonFactory
;
import
com.google.api.services.drive.Drive
;
import
com.google.api.services.drive.DriveScopes
;
import
com.google.auth.http.HttpCredentialsAdapter
;
import
com.google.auth.oauth2.GoogleCredentials
;
import
java.io.ByteArrayOutputStream
;
import
java.io.IOException
;
import
java.io.OutputStream
;
import
java.util.Arrays
;
/* Class to demonstrate use-case of drive's download file. */
public
class
DownloadFile
{
/**
* Download a Document file in PDF format.
*
* @param realFileId file ID of any workspace document format file.
* @return byte array stream if successful, {@code null} otherwise.
* @throws IOException if service account credentials file not found.
*/
public
static
ByteArrayOutputStream
downloadFile
(
String
realFileId
)
throws
IOException
{
/* Load pre-authorized user credentials from the environment.
TODO(developer) - See https://developers.google.com/identity for
guides on implementing OAuth2 for your application.*/
GoogleCredentials
credentials
=
GoogleCredentials
.
getApplicationDefault
()
.
createScoped
(
Arrays
.
asList
(
DriveScopes
.
DRIVE_FILE
));
HttpRequestInitializer
requestInitializer
=
new
HttpCredentialsAdapter
(
credentials
);
// Build a new authorized API client service.
Drive
service
=
new
Drive
.
Builder
(
new
NetHttpTransport
(),
GsonFactory
.
getDefaultInstance
(),
requestInitializer
)
.
setApplicationName
(
"Drive samples"
)
.
build
();
try
{
OutputStream
outputStream
=
new
ByteArrayOutputStream
();
service
.
files
().
get
(
realFileId
)
.
executeMediaAndDownloadTo
(
outputStream
);
return
(
ByteArrayOutputStream
)
outputStream
;
}
catch
(
GoogleJsonResponseException
e
)
{
// TODO(developer) - handle error appropriately
System
.
err
.
println
(
"Unable to move file: "
+
e
.
getDetails
());
throw
e
;
}
}
}
```


### Python


```
import
io
import
google.auth
from
googleapiclient.discovery
import
build
from
googleapiclient.errors
import
HttpError
from
googleapiclient.http
import
MediaIoBaseDownload
def
download_file
(
real_file_id
):
"""Downloads a file
Args:
real_file_id: ID of the file to download
Returns : IO object with location.
Load pre-authorized user credentials from the environment.
TODO(developer) - See https://developers.google.com/identity
for guides on implementing OAuth2 for the application.
"""
creds
,
_
=
google
.
auth
.
default
()
try
:
# create drive api client
service
=
build
(
"drive"
,
"v3"
,
credentials
=
creds
)
file_id
=
real_file_id
# pylint: disable=maybe-no-member
request
=
service
.
files
()
.
get_media
(
fileId
=
file_id
)
file
=
io
.
BytesIO
()
downloader
=
MediaIoBaseDownload
(
file
,
request
)
done
=
False
while
done
is
False
:
status
,
done
=
downloader
.
next_chunk
()
print
(
f
"Download
{
int
(
status
.
progress
()
*
100
)
}
."
)
except
HttpError
as
error
:
print
(
f
"An error occurred:
{
error
}
"
)
file
=
None
return
file
.
getvalue
()
if
__name__
==
"__main__"
:
download_file
(
real_file_id
=
"1KuPmvGq8yoYgbfW74OENMCB5H0n_2Jm9"
)
```


### Node.js


```
import
{
GoogleAuth
}
from
'google-auth-library'
;
import
{
google
}
from
'googleapis'
;
/**
* Downloads a file from Google Drive.
* @param {string} fileId The ID of the file to download.
* @return {Promise<number>} The status of the download.
*/
async
function
downloadFile
(
fileId
)
{
// Authenticate with Google and get an authorized client.
// TODO (developer): Use an appropriate auth mechanism for your app.
const
auth
=
new
GoogleAuth
({
scopes
:
'https://www.googleapis.com/auth/drive'
,
});
// Create a new Drive API client (v3).
const
service
=
google
.
drive
({
version
:
'v3'
,
auth
});
// Download the file.
const
file
=
await
service
.
files
.
get
({
fileId
,
alt
:
'media'
,
});
// Print the status of the download.
console
.
log
(
file
.
status
);
return
file
.
status
;
}
```


### PHP


```
<
?php
use Google\Client;
use Google\Service\Drive;
function downloadFile()
{
try {
$client = new Client();
$client->useApplicationDefaultCredentials();
$client->addScope(Drive::DRIVE);
$driveService = new Drive($client);
$realFileId = readline("Enter File Id: ");
$fileId = '0BwwA4oUTeiV1UVNwOHItT0xfa2M';
$fileId = $realFileId;
$response = $driveService->files->get($fileId, array(
'alt' => 'media'));
$content = $response->getBody()->getContents();
return $content;
} catch(Exception $e) {
echo "Error Message: ".$e;
}
}
```


### .NET


```
using
Google.Apis.Auth.OAuth2
;
using
Google.Apis.Download
;
using
Google.Apis.Drive.v3
;
using
Google.Apis.Services
;
namespace
DriveV3Snippets
{
// Class to demonstrate use-case of drive's download file.
public
class
DownloadFile
{
/// <summary>
/// Download a Document file in PDF format.
/// </summary>
/// <param name="fileId">file ID of any workspace document format file.</param>
/// <returns>byte array stream if successful, null otherwise.</returns>
public
static
MemoryStream
DriveDownloadFile
(
string
fileId
)
{
try
{
/* Load pre-authorized user credentials from the environment.
TODO(developer) - See https://developers.google.com/identity for
guides on implementing OAuth2 for your application. */
GoogleCredential
credential
=
GoogleCredential
.
GetApplicationDefault
()
.
CreateScoped
(
DriveService
.
Scope
.
Drive
);
// Create Drive API service.
var
service
=
new
DriveService
(
new
BaseClientService
.
Initializer
{
HttpClientInitializer
=
credential
,
ApplicationName
=
"Drive API Snippets"
});
var
request
=
service
.
Files
.
Get
(
fileId
);
var
stream
=
new
MemoryStream
();
// Add a handler which will be notified on progress changes.
// It will notify on each chunk download and when the
// download is completed or failed.
request
.
MediaDownloader
.
ProgressChanged
+=
progress
=
>
{
switch
(
progress
.
Status
)
{
case
DownloadStatus
.
Downloading
:
{
Console
.
WriteLine
(
progress
.
BytesDownloaded
);
break
;
}
case
DownloadStatus
.
Completed
:
{
Console
.
WriteLine
(
"Download complete."
);
break
;
}
case
DownloadStatus
.
Failed
:
{
Console
.
WriteLine
(
"Download failed."
);
break
;
}
}
};
request
.
Download
(
stream
);
return
stream
;
}
catch
(
Exception
e
)
{
// TODO(developer) - handle error appropriately
if
(
e
is
AggregateException
)
{
Console
.
WriteLine
(
"Credential Not found"
);
}
else
{
throw
;
}
}
return
null
;
}
}
}
```


### curl


```bash
curl
-L
"https://www.googleapis.com/drive/v3/files/
FILE_ID
?alt=media"
\
--header
"Authorization: Bearer
ACCESS_TOKEN
"
\
--output
"
FILE_NAME
"
```

Replace the following:

- FILE_ID
: the ID of the file to download.
- ACCESS_TOKEN
: the access token that grants access to
the API.
- FILE_NAME
: the name of the output file.
File downloads started from your app must be authorized with a scope that allows
read access to the file content. For example, an app using the
drive.readonly.metadata
scope isn't authorized to download the file contents.
The client library code samples use the restricted
drive
file scope that allows
users to view and manage all of your Drive files. To learn more
about Drive scopes, refer to
Choose Google Drive API scopes
.

Users with
owner
permissions (for my Drive files) or
organizer
permissions (for shared drive files) can restrict downloading
through the
DownloadRestrictionsMetadata
object. For more information, see
Prevent users from downloading, printing, or
copying your file
.

Files identified as
abusive
(such as harmful software) are only downloadable by the file owner.
Additionally, the
acknowledgeAbuse
query parameter must be set to
true
to
indicate that the user has acknowledged the risk of downloading potentially
unwanted software or other abusive files. Your application should interactively
warn the user before using this query parameter.


### Partial download

Partial download involves downloading only a specified portion of a file. You
can specify the portion of the file you want to download by using a
byte
range
with the
Range
header. For example:


```
Range: bytes=500-999
```


## Download blob file content at an earlier version

To download the content of blob files at an earlier version, use the
revisions.get
method with the ID of the
file to download, the ID of the revision, and the
alt
system
parameter
.
The
alt=media
parameter tells the server that a download of content is being
requested as an alternative response format. Similar to
files.get
, the
revisions.get
method also accepts the
acknowledgeAbuse
query parameter and
the
Range
header.

You can only download blob file content revisions that are marked as "Keep
Forever". If you want to download a revision, set it to "Keep Forever" first.
For more information, see
Specify revisions to save from auto delete
.

For additional information on downloading a revision, see
Manage long-running
operations
.


```bash
curl
-L
"https://www.googleapis.com/drive/v3/files/
FILE_ID
/revisions/
REVISION_ID
?alt=media"
\
--header
"Authorization: Bearer
ACCESS_TOKEN
"
\
--output
"
FILE_NAME
"
```

- REVISION_ID
: the ID of the revision to download.

## Download blob file content in a browser

To download the content of blob files stored on Drive within a
browser, instead of through the API, use the
webContentLink
field of the
files
resource. If the user has download access to the file,
a link for downloading the file and its contents is returned. You can either
redirect a user to this URL, or offer it as a clickable link.


```bash
curl
"https://www.googleapis.com/drive/v3/files/
FILE_ID
?fields=webContentLink"
\
--header
"Authorization: Bearer
ACCESS_TOKEN
"
\
--header
"Accept: application/json"
```

- FILE_ID
: the ID of the file to get the download link
for.

## Download blob file content using long-running operations

To download the content of blob files using long-running operations (LRO), use
the
files.download
method with the ID of
the file to download. You can optionally set the ID of the revision.

This is the only way to download Google Vids files. If you attempt to export
Google Vids files, you receive a
fileNotExportable
error.
For more information, see
Manage long-running
operations
.

The following curl command initiates a LRO and returns a JSON response. To
either download the file or poll this LRO you must make another request
using the returned ID to obtain the content URL. Then, you can make a final
curl request to that URL to download the file. For more information, see
Manage long-running
operations
.


```bash
curl
--request
POST
"https://www.googleapis.com/drive/v3/files/
FILE_ID
/download?mimeType=video/mp4"
\
--header
"Authorization: Bearer
ACCESS_TOKEN
"
\
--header
"Content-Length: 0"
\
--header
"Accept: application/json"
```


## Export Google Workspace document content

To export Google Workspace document byte content, use the
files.export
method with the ID of the file to export and
the correct MIME type. Exported content is limited to 10 MB.

The following code samples show how to use the
files.export
method to export a
Google Workspace document in PDF format:


```
/**
* Exports a Google Workspace document.
* @param {string} fileId The ID of the file to export.
* @param {string} mimeType The MIME type to export to.
* @return {Blob} The exported content as a Blob.
*/
function
exportPdf
(
fileId
,
mimeType
)
{
var
url
=
'https://www.googleapis.com/drive/v3/files/'
+
fileId
+
'/export?mimeType='
+
encodeURIComponent
(
mimeType
);
var
response
=
UrlFetchApp
.
fetch
(
url
,
{
headers
:
{
'Authorization'
:
'Bearer '
+
ScriptApp
.
getOAuthToken
()
}
});
return
response
.
getBlob
();
}
```


```
import
com.google.api.client.googleapis.json.GoogleJsonResponseException
;
import
com.google.api.client.http.HttpRequestInitializer
;
import
com.google.api.client.http.javanet.NetHttpTransport
;
import
com.google.api.client.json.gson.GsonFactory
;
import
com.google.api.services.drive.Drive
;
import
com.google.api.services.drive.DriveScopes
;
import
com.google.auth.http.HttpCredentialsAdapter
;
import
com.google.auth.oauth2.GoogleCredentials
;
import
java.io.ByteArrayOutputStream
;
import
java.io.IOException
;
import
java.io.OutputStream
;
import
java.util.Arrays
;
/* Class to demonstrate use-case of drive's export pdf. */
public
class
ExportPdf
{
/**
* Download a Document file in PDF format.
*
* @param realFileId file ID of any workspace document format file.
* @return byte array stream if successful, {@code null} otherwise.
* @throws IOException if service account credentials file not found.
*/
public
static
ByteArrayOutputStream
exportPdf
(
String
realFileId
)
throws
IOException
{
// Load pre-authorized user credentials from the environment.
// TODO(developer) - See https://developers.google.com/identity for
// guides on implementing OAuth2 for your application.
GoogleCredentials
credentials
=
GoogleCredentials
.
getApplicationDefault
()
.
createScoped
(
Arrays
.
asList
(
DriveScopes
.
DRIVE_FILE
));
HttpRequestInitializer
requestInitializer
=
new
HttpCredentialsAdapter
(
credentials
);
// Build a new authorized API client service.
Drive
service
=
new
Drive
.
Builder
(
new
NetHttpTransport
(),
GsonFactory
.
getDefaultInstance
(),
requestInitializer
)
.
setApplicationName
(
"Drive samples"
)
.
build
();
OutputStream
outputStream
=
new
ByteArrayOutputStream
();
try
{
service
.
files
().
export
(
realFileId
,
"application/pdf"
)
.
executeMediaAndDownloadTo
(
outputStream
);
return
(
ByteArrayOutputStream
)
outputStream
;
}
catch
(
GoogleJsonResponseException
e
)
{
// TODO(developer) - handle error appropriately
System
.
err
.
println
(
"Unable to export file: "
+
e
.
getDetails
());
throw
e
;
}
}
}
```


```
import
io
import
google.auth
from
googleapiclient.discovery
import
build
from
googleapiclient.errors
import
HttpError
from
googleapiclient.http
import
MediaIoBaseDownload
def
export_pdf
(
real_file_id
):
"""Download a Document file in PDF format.
Args:
real_file_id : file ID of any workspace document format file
Returns : IO object with location
Load pre-authorized user credentials from the environment.
TODO(developer) - See https://developers.google.com/identity
for guides on implementing OAuth2 for the application.
"""
creds
,
_
=
google
.
auth
.
default
()
try
:
# create drive api client
service
=
build
(
"drive"
,
"v3"
,
credentials
=
creds
)
file_id
=
real_file_id
# pylint: disable=maybe-no-member
request
=
service
.
files
()
.
export_media
(
fileId
=
file_id
,
mimeType
=
"application/pdf"
)
file
=
io
.
BytesIO
()
downloader
=
MediaIoBaseDownload
(
file
,
request
)
done
=
False
while
done
is
False
:
status
,
done
=
downloader
.
next_chunk
()
print
(
f
"Download
{
int
(
status
.
progress
()
*
100
)
}
."
)
except
HttpError
as
error
:
print
(
f
"An error occurred:
{
error
}
"
)
file
=
None
return
file
.
getvalue
()
if
__name__
==
"__main__"
:
export_pdf
(
real_file_id
=
"1zbp8wAyuImX91Jt9mI-CAX_1TqkBLDEDcr2WeXBbKUY"
)
```


```
import
{
GoogleAuth
}
from
'google-auth-library'
;
import
{
google
}
from
'googleapis'
;
/**
* Exports a Google Doc as a PDF.
* @param {string} fileId The ID of the file to export.
* @return {Promise<number>} The status of the export request.
*/
async
function
exportPdf
(
fileId
)
{
// Authenticate with Google and get an authorized client.
// TODO (developer): Use an appropriate auth mechanism for your app.
const
auth
=
new
GoogleAuth
({
scopes
:
'https://www.googleapis.com/auth/drive'
,
});
// Create a new Drive API client (v3).
const
service
=
google
.
drive
({
version
:
'v3'
,
auth
});
// Export the file as a PDF.
const
result
=
await
service
.
files
.
export
({
fileId
,
mimeType
:
'application/pdf'
,
});
// Print the status of the export.
console
.
log
(
result
.
status
);
return
result
.
status
;
}
```


```
<
?php
use Google\Client;
use Google\Service\Drive;
function exportPdf()
{
try {
$client = new Client();
$client->useApplicationDefaultCredentials();
$client->addScope(Drive::DRIVE);
$driveService = new Drive($client);
$realFileId = readline("Enter File Id: ");
$fileId = '1ZdR3L3qP4Bkq8noWLJHSr_iBau0DNT4Kli4SxNc2YEo';
$fileId = $realFileId;
$response = $driveService->files->export($fileId, 'application/pdf', array(
'alt' => 'media'));
$content = $response->getBody()->getContents();
return $content;
}  catch(Exception $e) {
echo "Error Message: ".$e;
}
}
```


```
using
Google.Apis.Auth.OAuth2
;
using
Google.Apis.Download
;
using
Google.Apis.Drive.v3
;
using
Google.Apis.Services
;
namespace
DriveV3Snippets
{
// Class to demonstrate use of Drive export pdf
public
class
ExportPdf
{
/// <summary>
/// Download a Document file in PDF format.
/// </summary>
/// <param name="fileId">Id of the file.</param>
/// <returns>Byte array stream if successful, null otherwise</returns>
public
static
MemoryStream
DriveExportPdf
(
string
fileId
)
{
try
{
/* Load pre-authorized user credentials from the environment.
TODO(developer) - See https://developers.google.com/identity for
guides on implementing OAuth2 for your application. */
GoogleCredential
credential
=
GoogleCredential
.
GetApplicationDefault
()
.
CreateScoped
(
DriveService
.
Scope
.
Drive
);
// Create Drive API service.
var
service
=
new
DriveService
(
new
BaseClientService
.
Initializer
{
HttpClientInitializer
=
credential
,
ApplicationName
=
"Drive API Snippets"
});
var
request
=
service
.
Files
.
Export
(
fileId
,
"application/pdf"
);
var
stream
=
new
MemoryStream
();
// Add a handler which will be notified on progress changes.
// It will notify on each chunk download and when the
// download is completed or failed.
request
.
MediaDownloader
.
ProgressChanged
+=
progress
=
>
{
switch
(
progress
.
Status
)
{
case
DownloadStatus
.
Downloading
:
{
Console
.
WriteLine
(
progress
.
BytesDownloaded
);
break
;
}
case
DownloadStatus
.
Completed
:
{
Console
.
WriteLine
(
"Download complete."
);
break
;
}
case
DownloadStatus
.
Failed
:
{
Console
.
WriteLine
(
"Download failed."
);
break
;
}
}
};
request
.
Download
(
stream
);
return
stream
;
}
catch
(
Exception
e
)
{
// TODO(developer) - handle error appropriately
if
(
e
is
AggregateException
)
{
Console
.
WriteLine
(
"Credential Not found"
);
}
else
{
throw
;
}
}
return
null
;
}
}
}
```


```bash
curl
-L
"https://www.googleapis.com/drive/v3/files/
FILE_ID
/export?mimeType=application/pdf"
\
--header
"Authorization: Bearer
ACCESS_TOKEN
"
\
--output
"
FILE_NAME
.pdf"
```

The client library code samples use the restricted
drive
scope that allows
users to view and manage all of your Drive files. To learn more
about Drive scopes, refer to
Choose Google Drive API scopes
.

The code samples also declare the export MIME type as
application/pdf
. For a
complete list of all export MIME types supported for each Google Workspace
document, refer to
Export MIME types for Google Workspace documents
.


## Export Google Workspace document content in a browser

To export Google Workspace document content within a browser, use the
exportLinks
field of the
files
resource. Depending on the document type, a
link to download the file and its contents is returned for every MIME type
available. You can either redirect a user to a URL, or offer it as a clickable
link.


```bash
curl
"https://www.googleapis.com/drive/v3/files/
FILE_ID
?fields=id,name,exportLinks"
\
--header
"Authorization: Bearer
ACCESS_TOKEN
"
\
--header
"Accept: application/json"
```


## Export Google Workspace document content at an earlier version in a browser

To export Google Workspace document content at an earlier version within a
browser, use the
revisions.get
method with
the ID of the file to download and the ID of the revision to generate an export
link from which you can perform the download. If the user has download access to
the file, a link for downloading the file and its contents is returned. You can
either redirect a user to this URL, or offer it as a clickable link.


```bash
curl
"https://www.googleapis.com/drive/v3/files/
FILE_ID
/revisions/
REVISION_ID
?fields=id,name,exportLinks"
\
--header
"Authorization: Bearer
ACCESS_TOKEN
"
\
--header
"Accept: application/json"
```


## Export Google Workspace document content using long-running operations

To export Google Workspace document content using long-running operations
(LRO), use the
files.download
method with
the ID of the file to download and the ID of the revision. For more information,
see
Manage long-running operations
.


```bash
curl
--request
POST
"https://www.googleapis.com/drive/v3/files/
FILE_ID
/download?mimeType=
MIME_TYPE
&revisionId=
REVISION_ID
"
\
--header
"Authorization: Bearer
ACCESS_TOKEN
"
\
--header
"Content-Length: 0"
\
--header
"Accept: application/json"
```

- MIME_TYPE
: the MIME type to export to.

## Related topics

- Protect file content
- Export MIME types for Google Workspace documents
Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2026-05-07 UTC.


---

# Manage file revisions Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/guides/manage-revisions

- Home
- Google Workspace
- Google Drive
- Guides
This guide explains how to use the
revisions
resource to manage file revisions, such as getting a file revision and
publishing a Google Workspace revision. The Google Drive API also lets you
download revisions. For more details about revision terminology, see
Changes
and revisions overview
.

To access the revision history, a user must have the
role
of
owner
,
organizer
,
fileOrganizer
, or
writer
.

To specify the fields to return in the response, you can set the
fields
system parameter
with any method of the
revisions
resource. If
you omit the parameter, the server returns a default set of fields. For example,
the
revisions.list
method only returns the
id
,
mimeType
,
kind
, and
modifiedTime
fields. To return different fields, see
Return specific fields
.


## Specify revisions to save from auto delete

Google Drive automatically deletes older revisions that are no longer of
interest to the user.

A
blob
file revision can be set to "Keep
Forever" meaning the revision cannot be automatically purged. Up to 200
revisions can be set to "Keep Forever" and they count towards your storage
limit. The head revision is never auto-purged.

Any blob file revision, other than the head revision, that's not designated as
"Keep Forever" is purgeable. Purgeable revisions are typically preserved for 30
days, but can be purged earlier if a file has 100 revisions that aren't
designated as "Keep Forever" and a new revision is uploaded.

You can set the boolean
keepForever
field of the
revisions
resource to
true
to mark revisions that you
don't want Drive to purge. Once a blob file revision is set to
"Keep Forever", it can only be downloaded or deleted. For more information, see
Download a revision
or
Delete a
revision
.

If you're using the older Drive API v2, use the
pinned
field of the
revisions
resource instead of
keepForever
.


## Get a file revision

To get a file revision's metadata or content, use the
get
method on the
revisions
resource with the
fileId
and
revisionId
path parameters. If you don't know the revision ID, you can
list
all revisions on a file
using the
list
method.

The method returns the revision's metadata as an instance of a
revisions
resource. If you provide the
alt=media
parameter, then the response includes
the revision's contents in the response body. To download a blob file, see
Download blob file content at an earlier version
.

To acknowledge the risk of downloading known malware or other
abusive
files, set the
acknowledgeAbuse
query parameter to
true
. This field is only applicable when
the
alt=media
parameter is set and the user is either the file owner or an
organizer of the shared drive in which the file resides.


## List a file's revisions

To list a file's revisions, use the
list
method on the
revisions
resource with the
fileId
path parameter. The method returns a list of file revisions.

Pass the following query parameters to customize pagination of, or filter,
revisions:

- pageSize
: The maximum number of revisions to return per page.
pageSize
: The maximum number of revisions to return per page.

- pageToken
: A page token, received from a previous list call. Provide this
token to retrieve the subsequent page.
pageToken
: A page token, received from a previous list call. Provide this
token to retrieve the subsequent page.


## Update a file revision

To update a revision on a file, use the
update
method on the
revisions
resource with the
fileId
and
revisionId
path
parameters.

The method returns an instance of a
revisions
resource.


## Download a revision

You can only download blob file content revisions marked as "Keep Forever". If
you want to download a revision, make sure to set it to "Keep Forever" first.
For more information, see
Specify revisions to save from auto
delete
.

To download a blob file content revision or to export a Google Workspace
document content revision, see
Download and export
files
.


## Delete a file revision

To permanently delete a file revision, use the
delete
method on the
revisions
resource with the
fileId
and
revisionId
path
parameters.

You can only delete revisions for blob files with binary content in
Drive, such as images, videos, and PDFs. You can delete a blob
file revision when it's marked as "Keep Forever." Revisions for other files,
such as a Google Docs or Sheets, and the last remaining
revision of the binary file, can't be deleted.


## Publish a revision

To publish a Google Docs, Google Sheets, and Google Slides revision, set
the
published
property for that file in the
revisions
resource. This property can't be set
for Google Sites revisions using Drive API.

Published revisions don't reflect changes made to a file unless the
publishAuto
property is set. If the property is set to
true
, newer revisions
of a file are automatically published, overwriting the previous ones.
Slides and Drawings only support automatic
re-publishing and require the
publishAuto
property to be set to
true
. For
Sites files,
publishAuto
is always
false
.

If the file is created in a Google Workspace domain, the
publishedOutsideDomain
property indicates whether the revision is accessible
by anyone or if it's restricted to users of the domain. For Sites
files, this property indicates whether a
type=anyone
permission exists. For
more information, see the
type
field on the
permissions
resource.

Automatic publishing is also controlled by the "Automatically republish when
changes are made" checkbox in the UI of Docs and
Sheets. For more information, see
Make Google Docs,
Sheets, Slides & Forms
public
.


## Related topics

- Download and export files
- Roles and permissions
Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2026-05-07 UTC.


---

# Manage shared drives Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/guides/manage-shareddrives

- Home
- Google Workspace
- Google Drive
- Guides
This guide contains tasks related to managing shared drives, such as creating
shared drives and managing members and permissions, using the Google Drive API.

If you want to specify the fields to return in the response, you can set the
fields
system
parameter
with any method of the
drives
resource. If you
don't specify the
fields
parameter, the server returns a default set of fields
specific to the method. For example, the
list
method returns only the
kind
,
id
,
and
name
fields for each shared drive. For more information, see
Return
specific fields
.

To learn more about shared drive folder limits, see
Shared drive folder
limits
.


## Create a shared drive

To create a shared drive, use the
create
method on the
drives
resource with the
requestId
parameter.

The
requestId
parameter identifies the logical attempt for idempotent creation
of a shared drive. If the request times out or returns an indeterminate backend
error, the same request can be repeated and won't create duplicates. The
requestId
and body of the request must remain the same.

The following code sample shows how to create a shared drive:


### Java


```
import
com.google.api.client.googleapis.json.GoogleJsonResponseException
;
import
com.google.api.client.http.HttpRequestInitializer
;
import
com.google.api.client.http.javanet.NetHttpTransport
;
import
com.google.api.client.json.gson.GsonFactory
;
import
com.google.api.services.drive.DriveScopes
;
import
com.google.api.services.drive.model.Drive
;
import
com.google.auth.http.HttpCredentialsAdapter
;
import
com.google.auth.oauth2.GoogleCredentials
;
import
java.io.IOException
;
import
java.util.Arrays
;
import
java.util.UUID
;
/* class to demonstrate use-case of Drive's create drive. */
public
class
CreateDrive
{
/**
* Create a drive.
*
* @return Newly created drive id.
* @throws IOException if service account credentials file not found.
*/
public
static
String
createDrive
()
throws
IOException
{
/*Load pre-authorized user credentials from the environment.
TODO(developer) - See https://developers.google.com/identity for
guides on implementing OAuth2 for your application.*/
GoogleCredentials
credentials
=
GoogleCredentials
.
getApplicationDefault
().
createScoped
(
Arrays
.
asList
(
DriveScopes
.
DRIVE
));
HttpRequestInitializer
requestInitializer
=
new
HttpCredentialsAdapter
(
credentials
);
// Build a new authorized API client service.
com
.
google
.
api
.
services
.
drive
.
Drive
service
=
new
com
.
google
.
api
.
services
.
drive
.
Drive
.
Builder
(
new
NetHttpTransport
(),
GsonFactory
.
getDefaultInstance
(),
requestInitializer
)
.
setApplicationName
(
"Drive samples"
)
.
build
();
Drive
driveMetadata
=
new
Drive
();
driveMetadata
.
setName
(
"Project Resources"
);
String
requestId
=
UUID
.
randomUUID
().
toString
();
try
{
Drive
drive
=
service
.
drives
().
create
(
requestId
,
driveMetadata
)
.
execute
();
System
.
out
.
println
(
"Drive ID: "
+
drive
.
getId
());
return
drive
.
getId
();
}
catch
(
GoogleJsonResponseException
e
)
{
// TODO(developer) - handle error appropriately
System
.
err
.
println
(
"Unable to create drive: "
+
e
.
getDetails
());
throw
e
;
}
}
}
```


### Python


```
import
uuid
import
google.auth
from
googleapiclient.discovery
import
build
from
googleapiclient.errors
import
HttpError
def
create_drive
():
"""Create a drive.
Returns:
Id of the created drive
Load pre-authorized user credentials from the environment.
TODO(developer) - See https://developers.google.com/identity
for guides on implementing OAuth2 for the application.
"""
creds
,
_
=
google
.
auth
.
default
()
try
:
# create drive api client
service
=
build
(
"drive"
,
"v3"
,
credentials
=
creds
)
drive_metadata
=
{
"name"
:
"Project Resources"
}
request_id
=
str
(
uuid
.
uuid4
())
# pylint: disable=maybe-no-member
drive
=
(
service
.
drives
()
.
create
(
body
=
drive_metadata
,
requestId
=
request_id
,
fields
=
"id"
)
.
execute
()
)
print
(
f
'Drive ID:
{
drive
.
get
(
"id"
)
}
'
)
except
HttpError
as
error
:
print
(
f
"An error occurred:
{
error
}
"
)
drive
=
None
return
drive
.
get
(
"id"
)
if
__name__
==
"__main__"
:
create_drive
()
```


### Node.js


```
import
{
GoogleAuth
}
from
'google-auth-library'
;
import
{
google
}
from
'googleapis'
;
import
{
v4
as
uuid
}
from
'uuid'
;
/**
* Creates a new shared drive.
* @return {Promise<string>} The ID of the created shared drive.
*/
async
function
createDrive
()
{
// Authenticate with Google and get an authorized client.
// TODO (developer): Use an appropriate auth mechanism for your app.
const
auth
=
new
GoogleAuth
({
scopes
:
'https://www.googleapis.com/auth/drive'
,
});
// Create a new Drive API client (v3).
const
service
=
google
.
drive
({
version
:
'v3'
,
auth
});
// The metadata for the new shared drive.
const
driveMetadata
=
{
name
:
'Project resources'
,
};
// A unique request ID to avoid creating duplicate shared drives.
const
requestId
=
uuid
();
// Create the new shared drive.
const
Drive
=
await
service
.
drives
.
create
({
requestBody
:
driveMetadata
,
requestId
,
fields
:
'id'
,
});
// Print the ID of the new shared drive.
console
.
log
(
'Drive Id:'
,
Drive
.
data
.
id
);
if
(
!
Drive
.
data
.
id
)
{
throw
new
Error
(
'Drive ID not found.'
);
}
return
Drive
.
data
.
id
;
}
```


### PHP


```
<
?php
use Google\Client;
use Google\Service\Drive;
use Ramsey\Uuid\Uuid;
function createDrive()
{
try {
$client = new Client();
$client->useApplicationDefaultCredentials();
$client->addScope(Drive::DRIVE);
$driveService = new Drive($client);
$driveMetadata = new Drive\Drive(array(
'name' => 'Project Resources'));
$requestId = Uuid::uuid4()->toString();
$drive = $driveService->drives->create($requestId, $driveMetadata, array(
'fields' => 'id'));
printf("Drive ID: %s\n", $drive->id);
return $drive->id;
} catch(Exception $e)  {
echo "Error Message: ".$e;
}
}
```


### .NET


```
using
Google.Apis.Auth.OAuth2
;
using
Google.Apis.Drive.v3
;
using
Google.Apis.Drive.v3.Data
;
using
Google.Apis.Services
;
namespace
DriveV3Snippets
{
// Class to demonstrate use of Drive's create drive.
public
class
CreateDrive
{
/// <summary>
/// Create a drive.
/// </summary>
/// <returns>newly created drive Id.</returns>
public
static
string
DriveCreateDrive
()
{
try
{
/* Load pre-authorized user credentials from the environment.
TODO(developer) - See https://developers.google.com/identity for
guides on implementing OAuth2 for your application. */
GoogleCredential
credential
=
GoogleCredential
.
GetApplicationDefault
()
.
CreateScoped
(
DriveService
.
Scope
.
Drive
);
// Create Drive API service.
var
service
=
new
DriveService
(
new
BaseClientService
.
Initializer
{
HttpClientInitializer
=
credential
,
ApplicationName
=
"Drive API Snippets"
});
var
driveMetadata
=
new
Drive
()
{
Name
=
"Project Resources"
};
var
requestId
=
Guid
.
NewGuid
().
ToString
();
var
request
=
service
.
Drives
.
Create
(
driveMetadata
,
requestId
);
request
.
Fields
=
"id"
;
var
drive
=
request
.
Execute
();
Console
.
WriteLine
(
"Drive ID: "
+
drive
.
Id
);
return
drive
.
Id
;
}
catch
(
Exception
e
)
{
// TODO(developer) - handle error appropriately
if
(
e
is
AggregateException
)
{
Console
.
WriteLine
(
"Credential Not found"
);
}
else
{
throw
;
}
}
return
null
;
}
}
}
```

Calls to the
create
method are
idempotent.

If the shared drive was successfully created on a previous request or due to a
retry, the method returns an instance of the
drives
resource. Sometimes, such
as after a prolonged time or if the body of the request has changed, a
409
error might be returned indicating the
requestId
must be discarded.


## Get a shared drive

To get metadata for a shared drive, use the
get
method on the
drives
resource with the
driveId
path parameter. If you
don't know the drive ID, you can
list all shared drives
using the
list
method.

The
get
method returns a shared drive as an instance of a
drives
resource.

To issue the request as a domain administrator, set the
useDomainAdminAccess
query parameter to
true
. For more information, see
Manage shared drives as
domain administrators
.


## List shared drives

To list a user's shared drives, use the
list
method on the
drives
resource. The method returns
a list of shared drives.

Pass the following query parameters to customize pagination of, or to filter,
shared drives:

- pageSize
: The maximum number of shared drives to return per page.
pageSize
: The maximum number of shared drives to return per page.

- pageToken
: A page token, received from a previous list call. Provide this
token to retrieve the subsequent page.
pageToken
: A page token, received from a previous list call. Provide this
token to retrieve the subsequent page.

- q
: Query string for searching shared drives. For more information, see
Search for shared drives
.
q
: Query string for searching shared drives. For more information, see
Search for shared drives
.

- useDomainAdminAccess
: Set to
true
to issue the request as a domain
administrator to return all shared drives of the domain in which the
requester is an administrator. For more information, see
Manage shared
drives as domain administrators
.
useDomainAdminAccess
: Set to
true
to issue the request as a domain
administrator to return all shared drives of the domain in which the
requester is an administrator. For more information, see
Manage shared
drives as domain administrators
.


## Update a shared drive

To update the metadata for a shared drive, use the
update
method on the
drives
resource with the
driveId
path
parameter.

The method returns a shared drive as an instance of a
drives
resource.


## Hide and unhide a shared drive

To hide a shared drive from the default view, use the
hide
method on the
drives
resource with the
driveId
parameter.

When a shared drive is hidden, Drive marks the shared drive
resource as
hidden=true
. Hidden shared drives don't appear in the
Drive UI or in the list of returned files.

To restore a shared drive to the default view, use the
unhide
method on the
drives
resource with the
driveId
parameter.

Both methods return a shared drive as an instance of a
drives
resource.


## Delete a shared drive

To permanently delete a shared drive, use the
delete
method on the
drives
resource with the
driveId
parameter.

Before deleting a shared drive, all content in the shared drive must be moved to
the trash or deleted. The user must also have
role=organizer
on the shared
drive folder. For more information, see
Trash or delete files and folders
.

Pass the following query parameters to filter shared drives:

- allowItemDeletion
: Set to
true
to delete items within the shared drive.
Only supported when
useDomainAdminAccess
is also set to
true
.
allowItemDeletion
: Set to
true
to delete items within the shared drive.
Only supported when
useDomainAdminAccess
is also set to
true
.


## Add or remove shared drive members

Add or remove shared drive members using the
permissions
resource.

To add a member, create the permission on the shared drive. Permission methods
can also be used on individual files within a shared drive to grant members
additional privileges or allow non-members to collaborate on specific items.

For more information and sample code, see
Share files, folders, and drives
.


## Manage shared drives as domain administrators

Apply the
useDomainAdminAccess
parameter with the
drives
and
permissions
resources to manage shared drives across an organization.

Users calling these methods with
useDomainAdminAccess=true
must have the
Drive and Docs
administrator
privilege
.
Administrators can
search for shared
drives
or update permissions for shared
drives owned by their organization, regardless of the administrator's membership
in any given shared drive.

When using service accounts, you might have to impersonate an authenticated
administrator using
service account
impersonation
.
Note that service accounts
do not
belong to your Google Workspace domain,
unlike user accounts. If you share Google Workspace assets, like documents or
events, with your entire Google Workspace domain, they're not shared with
service accounts. For more information, see
Service accounts
overview
.


### Recover a shared drive that doesn't have an organizer

The following code sample shows how to recover shared drives that no longer have
an organizer.


```
import
com.google.api.client.http.HttpRequestInitializer
;
import
com.google.api.client.http.javanet.NetHttpTransport
;
import
com.google.api.client.json.gson.GsonFactory
;
import
com.google.api.services.drive.DriveScopes
;
import
com.google.api.services.drive.model.Drive
;
import
com.google.api.services.drive.model.DriveList
;
import
com.google.api.services.drive.model.Permission
;
import
com.google.auth.http.HttpCredentialsAdapter
;
import
com.google.auth.oauth2.GoogleCredentials
;
import
java.io.IOException
;
import
java.util.ArrayList
;
import
java.util.Arrays
;
import
java.util.List
;
/* class to demonstrate use-case of Drive's shared drive without an organizer. */
public
class
RecoverDrive
{
/**
* Find all shared drives without an organizer and add one.
*
* @param realUser User's email id.
* @return All shared drives without an organizer.
* @throws IOException if shared drive not found.
*/
public
static
List<Drive>
recoverDrives
(
String
realUser
)
throws
IOException
{
/*Load pre-authorized user credentials from the environment.
TODO(developer) - See https://developers.google.com/identity for
guides on implementing OAuth2 for your application.*/
GoogleCredentials
credentials
=
GoogleCredentials
.
getApplicationDefault
().
createScoped
(
Arrays
.
asList
(
DriveScopes
.
DRIVE
));
HttpRequestInitializer
requestInitializer
=
new
HttpCredentialsAdapter
(
credentials
);
// Build a new authorized API client service.
com
.
google
.
api
.
services
.
drive
.
Drive
service
=
new
com
.
google
.
api
.
services
.
drive
.
Drive
.
Builder
(
new
NetHttpTransport
(),
GsonFactory
.
getDefaultInstance
(),
requestInitializer
)
.
setApplicationName
(
"Drive samples"
)
.
build
();
List<Drive>
drives
=
new
ArrayList<Drive>
();
// Find all shared drives without an organizer and add one.
// Note: This example does not capture all cases. Shared drives
// that have an empty group as the sole organizer, or an
// organizer outside the organization are not captured. A
// more exhaustive approach would evaluate each shared drive
// and the associated permissions and groups to ensure an active
// organizer is assigned.
String
pageToken
=
null
;
Permission
newOrganizerPermission
=
new
Permission
()
.
setType
(
"user"
)
.
setRole
(
"organizer"
);
newOrganizerPermission
.
setEmailAddress
(
realUser
);
do
{
DriveList
result
=
service
.
drives
().
list
()
.
setQ
(
"organizerCount = 0"
)
.
setFields
(
"nextPageToken, drives(id, name)"
)
.
setUseDomainAdminAccess
(
true
)
.
setPageToken
(
pageToken
)
.
execute
();
for
(
Drive
drive
:
result
.
getDrives
())
{
System
.
out
.
printf
(
"Found drive without organizer: %s (%s)\n"
,
drive
.
getName
(),
drive
.
getId
());
// Note: For improved efficiency, consider batching
// permission insert requests
Permission
permissionResult
=
service
.
permissions
()
.
create
(
drive
.
getId
(),
newOrganizerPermission
)
.
setUseDomainAdminAccess
(
true
)
.
setSupportsAllDrives
(
true
)
.
setFields
(
"id"
)
.
execute
();
System
.
out
.
printf
(
"Added organizer permission: %s\n"
,
permissionResult
.
getId
());
}
drives
.
addAll
(
result
.
getDrives
());
pageToken
=
result
.
getNextPageToken
();
}
while
(
pageToken
!=
null
);
return
drives
;
}
}
```


```
import
google.auth
from
googleapiclient.discovery
import
build
from
googleapiclient.errors
import
HttpError
def
recover_drives
(
real_user
):
"""Find all shared drives without an organizer and add one.
Args:
real_user:User ID for the new organizer.
Returns:
drives object
Load pre-authorized user credentials from the environment.
TODO(developer) - See https://developers.google.com/identity
for guides on implementing OAuth2 for the application.
"""
creds
,
_
=
google
.
auth
.
default
()
try
:
# create drive api client
service
=
build
(
"drive"
,
"v3"
,
credentials
=
creds
)
drives
=
[]
# pylint: disable=maybe-no-member
page_token
=
None
new_organizer_permission
=
{
"type"
:
"user"
,
"role"
:
"organizer"
,
"emailAddress"
:
"user@example.com"
,
}
new_organizer_permission
[
"emailAddress"
]
=
real_user
while
True
:
response
=
(
service
.
drives
()
.
list
(
q
=
"organizerCount = 0"
,
fields
=
"nextPageToken, drives(id, name)"
,
useDomainAdminAccess
=
True
,
pageToken
=
page_token
,
)
.
execute
()
)
for
drive
in
response
.
get
(
"drives"
,
[]):
print
(
"Found shared drive without organizer: "
f
"
{
drive
.
get
(
'title'
)
}
,
{
drive
.
get
(
'id'
)
}
"
)
permission
=
(
service
.
permissions
()
.
create
(
fileId
=
drive
.
get
(
"id"
),
body
=
new_organizer_permission
,
useDomainAdminAccess
=
True
,
supportsAllDrives
=
True
,
fields
=
"id"
,
)
.
execute
()
)
print
(
f
'Added organizer permission:
{
permission
.
get
(
"id"
)
}
'
)
drives
.
extend
(
response
.
get
(
"drives"
,
[]))
page_token
=
response
.
get
(
"nextPageToken"
,
None
)
if
page_token
is
None
:
break
except
HttpError
as
error
:
print
(
f
"An error occurred:
{
error
}
"
)
return
drives
if
__name__
==
"__main__"
:
recover_drives
(
real_user
=
"gduser1@workspacesamples.dev"
)
```


```
import
{
GoogleAuth
}
from
'google-auth-library'
;
import
{
google
}
from
'googleapis'
;
/**
* Finds all shared drives without an organizer and adds one.
* @param {string} userEmail The email of the user to assign ownership to.
* @return {Promise<object[]>} A list of the recovered drives.
*/
async
function
recoverDrives
(
userEmail
)
{
// Authenticate with Google and get an authorized client.
// TODO (developer): Use an appropriate auth mechanism for your app.
const
auth
=
new
GoogleAuth
({
scopes
:
'https://www.googleapis.com/auth/drive'
,
});
// Create a new Drive API client (v3).
const
service
=
google
.
drive
({
version
:
'v3'
,
auth
});
// The permission to add to the shared drive.
const
newOrganizerPermission
=
{
type
:
'user'
,
role
:
'organizer'
,
emailAddress
:
userEmail
,
// e.g., 'user@example.com'
};
// List all shared drives with no organizers.
const
result
=
await
service
.
drives
.
list
({
q
:
'organizerCount = 0'
,
fields
:
'nextPageToken, drives(id, name)'
,
useDomainAdminAccess
:
true
,
});
// Add the new organizer to each found shared drive.
for
(
const
drive
of
result
.
data
.
drives
??
[])
{
if
(
!
drive
.
id
)
{
continue
;
}
console
.
log
(
'Found shared drive without organizer:'
,
drive
.
name
,
drive
.
id
);
await
service
.
permissions
.
create
({
requestBody
:
newOrganizerPermission
,
fileId
:
drive
.
id
,
useDomainAdminAccess
:
true
,
supportsAllDrives
:
true
,
fields
:
'id'
,
});
}
return
result
.
data
.
drives
??
[];
}
```


```
<
?php
use Google\Client;
use Google\Service\Drive;
use Ramsey\Uuid\Uuid;
function recoverDrives()
{
try {
$client = new Client();
$client->useApplicationDefaultCredentials();
$client->addScope(Drive::DRIVE);
$driveService = new Drive($client);
$realUser = readline("Enter user email address: ");
$drives = array();
// Find all shared drives without an organizer and add one.
// Note: This example does not capture all cases. Shared drives
// that have an empty group as the sole organizer, or an
// organizer outside the organization are not captured. A
// more exhaustive approach would evaluate each shared drive
// and the associated permissions and groups to ensure an active
// organizer is assigned.
$pageToken = null;
$newOrganizerPermission = new Drive\Permission(array(
'type' => 'user',
'role' => 'organizer',
'emailAddress' => 'user@example.com'
));
$newOrganizerPermission['emailAddress'] = $realUser;
do {
$response = $driveService->drives->listDrives(array(
'q' => 'organizerCount = 0',
'fields' => 'nextPageToken, drives(id, name)',
'useDomainAdminAccess' => true,
'pageToken' => $pageToken
));
foreach ($response->drives as $drive) {
printf("Found shared drive without organizer: %s (%s)\n",
$drive->name, $drive->id);
$permission = $driveService->permissions->create($drive->id,
$newOrganizerPermission,
array(
'fields' => 'id',
'useDomainAdminAccess' => true,
'supportsAllDrives' => true
));
printf("Added organizer permission: %s\n", $permission->id);
}
array_push($drives, $response->drives);
$pageToken = $response->pageToken;
} while ($pageToken != null);
return $drives;
} catch(Exception $e) {
echo "Error Message: ".$e;
}
}
```


```
using
Google.Apis.Auth.OAuth2
;
using
Google.Apis.Drive.v3
;
using
Google.Apis.Drive.v3.Data
;
using
Google.Apis.Services
;
namespace
DriveV3Snippets
{
// Class to demonstrate use-case of Drive's shared drive without an organizer.
public
class
RecoverDrives
{
/// <summary>
/// Find all shared drives without an organizer and add one.
/// </summary>
/// <param name="realUser">User ID for the new organizer.</param>
/// <returns>all shared drives without an organizer.</returns>
public
static
IList<Drive>
DriveRecoverDrives
(
string
realUser
)
{
try
{
/* Load pre-authorized user credentials from the environment.
TODO(developer) - See https://developers.google.com/identity for
guides on implementing OAuth2 for your application. */
GoogleCredential
credential
=
GoogleCredential
.
GetApplicationDefault
()
.
CreateScoped
(
DriveService
.
Scope
.
Drive
);
// Create Drive API service.
var
service
=
new
DriveService
(
new
BaseClientService
.
Initializer
{
HttpClientInitializer
=
credential
,
ApplicationName
=
"Drive API Snippets"
});
var
drives
=
new
List<Drive>
();
// Find all shared drives without an organizer and add one.
// Note: This example does not capture all cases. Shared drives
// that have an empty group as the sole organizer, or an
// organizer outside the organization are not captured. A
// more exhaustive approach would evaluate each shared drive
// and the associated permissions and groups to ensure an active
// organizer is assigned.
string
pageToken
=
null
;
var
newOrganizerPermission
=
new
Permission
()
{
Type
=
"user"
,
Role
=
"organizer"
,
EmailAddress
=
realUser
};
do
{
var
request
=
service
.
Drives
.
List
();
request
.
UseDomainAdminAccess
=
true
;
request
.
Q
=
"organizerCount = 0"
;
request
.
Fields
=
"nextPageToken, drives(id, name)"
;
request
.
PageToken
=
pageToken
;
var
result
=
request
.
Execute
();
foreach
(
var
drive
in
result
.
Drives
)
{
Console
.
WriteLine
((
"Found abandoned shared drive: {0} ({1})"
,
drive
.
Name
,
drive
.
Id
));
// Note: For improved efficiency, consider batching
// permission insert requests
var
permissionRequest
=
service
.
Permissions
.
Create
(
newOrganizerPermission
,
drive
.
Id
);
permissionRequest
.
UseDomainAdminAccess
=
true
;
permissionRequest
.
SupportsAllDrives
=
true
;
permissionRequest
.
Fields
=
"id"
;
var
permissionResult
=
permissionRequest
.
Execute
();
Console
.
WriteLine
(
"Added organizer permission: {0}"
,
permissionResult
.
Id
);
}
pageToken
=
result
.
NextPageToken
;
}
while
(
pageToken
!=
null
);
return
drives
;
}
catch
(
Exception
e
)
{
// TODO(developer) - handle error appropriately
if
(
e
is
AggregateException
)
{
Console
.
WriteLine
(
"Credential Not found"
);
}
else
{
throw
;
}
}
return
null
;
}
}
}
```


## Prevent users from downloading, printing, or copying your file

You can limit how users can download, print, and copy files within shared
drives.

To determine whether the user can change organizer-applied download restrictions
of a shared drive, check the
capabilities.canChangeDownloadRestriction
boolean field. If
capabilities.canChangeDownloadRestriction
is set to
true
, download
restrictions can be applied to the shared drive. For more information, see
Understand file capabilities
.

The
drives
resource contains a collection of
boolean
restrictions
fields used to indicate whether an action can be performed on a shared drive.
Restrictions apply to a shared drive or items inside a shared drive.
Restrictions can be set using the
drives.update
method.

To apply download restrictions to a shared drive, a shared drive manager can set
the
restrictions.downloadRestriction
field of the
drives
resource using the
DownloadRestriction
object.
Setting the
restrictedForReaders
boolean field to
true
declares that both
download and copy are restricted for readers. Setting the
restrictedForWriters
boolean field to
true
declares that both download and copy are restricted for
writers. Note that if the
restrictedForWriters
field is
true
, download and
copy is also restricted for readers. Similarly, setting
restrictedForWriters
to
true
and
restrictedForReaders
to
false
is equivalent to setting both
restrictedForWriters
and
restrictedForReaders
to
true
.


### Backward compatibility

With the introduction of the
DownloadRestriction
object, the functionality of the
restrictions.copyRequiresWriterPermission
boolean field has been updated.

Now, setting
restrictions.copyRequiresWriterPermission
to
true
updates the
restrictedForReaders
boolean field of the
DownloadRestriction
object to
true
to declare that
both download and copy are restricted for readers.

Setting the
copyRequiresWriterPermission
field to
false
updates both the
restrictedForWriters
and
restrictedForReaders
fields to
false
. This means
download or copy restriction settings are removed for all users.


### Fields that control download, print, and copy features

The following table lists
drives
resource fields
that affect download, print, and copy functionality:


| Field | Description | Version |
| --- | --- | --- |
| capabilities.canCopy | Whether the current user can copy files in a shared drive. | v2 & v3 |
| capabilities.canDownload | Whether the current user can download files in a shared drive. | v2 & v3 |
| capabilities.canChangeCopyRequiresWriterPermission | Whether the current user can change the
copyRequiresWriterPermission
restriction of a shared drive. | v2 & v3 |
| capabilities.canResetDriveRestrictions | Whether the current user can reset the shared drive restrictions to defaults. | v2 & v3 |
| capabilities.canChangeDownloadRestriction | Whether the current user can change the download restriction of a shared drive. | v3 only |
| restrictions.copyRequiresWriterPermission | Whether the options to copy, print, or download files inside a shared drive are disabled for readers and commenters. When
true
, it sets the similarly named field to
true
for any file inside this shared drive. | v2 & v3 |
| restrictions.downloadRestriction | The download restrictions applied by shared drive managers. | v3 only |


## Folder limits

Shared drive folders have some storage limits. For information, see
Shared
drive limits in
Google Drive
.


### Item cap

Each user's shared drive has a limit of 500,000 items, including files, folders,
and shortcuts.

When the limit is reached, the shared drive can no longer accept items. To
resume receiving files, users must permanently delete items from the shared
drive. Note that items in the trash count toward the limit, but
permanently-deleted items don't. For more information, see
Trash or delete
files and folders
.


### Folder-depth limit

A folder in a shared drive can't contain more than 100 levels of nested folders.
This means that a child folder cannot be stored under a folder that's more than
99 levels deep. This limitation only applies to child folders.

Attempts to add more than 100 levels of folders returns a
teamDriveHierarchyTooDeep
HTTP status code response.


## Related topics

- File and folder limits in files
- Roles and permissions
Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2026-04-20 UTC.


---

# Share files, folders, and drives Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/guides/manage-sharing

- Home
- Google Workspace
- Google Drive
- Guides
Every Google Drive file, folder, and shared drive have associated
permissions
resources. Each resource
identifies the permission for a specific
type
(
user
,
group
,
domain
,
anyone
) and
role
(
owner
,
organizer
,
fileOrganizer
,
writer
,
commenter
,
reader
). For example, a
file might have a permission granting a specific user (
type=user
) read-only
access (
role=reader
) while another permission grants members of a specific
group (
type=group
) the ability to add comments to a file (
role=commenter
).

For a complete list of roles and the operations permitted by each, see
Roles
and permissions
.


## How permissions work

Permission lists for a folder propagate downward. All child files and folders
inherit permissions from the parent. Whenever permissions or the hierarchy is
changed, the propagation occurs recursively through all nested folders. For
example, if a file exists in a folder and that folder is then moved within
another folder, the permissions on the new folder propagate to the file. If the
new folder grants the file user a new role, such as "writer," it overrides their
old role.

Conversely, if a file inherits
role=writer
from a folder, and is moved to
another folder that provides a "reader" role, the file now inherits
role=reader
.

Inherited permissions cannot be removed or reduced on any item. Instead, these
permissions must be adjusted on the parent where they originate or a folder in
the hierarchy must enable the
limited access setting
.

Inherited permissions can be increased on an item. If a permission is increased
on a child, changing the permission of a parent does not affect the child's
permission unless the new parent permission is greater than the child.

Concurrent permissions operations on the same file aren't supported. Only the
last update is applied.


## Understand file capabilities

The
permissions
resource doesn't ultimately
determine the current user's ability to perform actions on a file or folder.
Instead, the
files
resource contains a collection
of boolean
capabilities
fields used to indicate whether an action can be performed on a file or folder.
The Google Drive API sets these fields based on the current user's
permissions
resource associated with the file or folder.

For example, when Alex logs into your app and tries to share a file, Alex's role
is checked for permissions on the file. If the role allows them to share a file,
the
capabilities
related to the file, such as
canShare
, are set relative to
the role. If Alex wants to share the file, your app checks the
capabilities
to
ensure
canShare
is set to
true
.


### Get file capabilities

When your app opens a file, it should check the file's capabilities and render
the UI to reflect the permissions of the current user. For example, if the user
doesn't have the
canComment
capability on the file, the ability to comment
should be disabled in the UI.

To check the capabilities, call the
get
method on the
files
resource with the
fileId
path parameter and the
fields
parameter set to the
capabilities
field. For
further information on returning fields using the
fields
parameter, see
Return specific fields
.

The following code sample shows how to verify user permissions. The response returns a list of capabilities the user has on the file. Each capability corresponds to a fine-grained action that a user can take. Some fields are only populated for items in shared drives.

Request


```bash
GET https://www.googleapis.com/drive/v3/files/
FILE_ID
?fields=capabilities
```

Response


```
{
"capabilities"
:
{
"canAcceptOwnership"
:
false
,
"canAddChildren"
:
false
,
"canAddMyDriveParent"
:
false
,
"canChangeCopyRequiresWriterPermission"
:
true
,
"canChangeItemDownloadRestriction"
:
true
,
"canChangeSecurityUpdateEnabled"
:
false
,
"canChangeViewersCanCopyContent"
:
true
,
"canComment"
:
true
,
"canCopy"
:
true
,
"canDelete"
:
true
,
"canDisableInheritedPermissions"
:
false
,
"canDownload"
:
true
,
"canEdit"
:
true
,
"canEnableInheritedPermissions"
:
true
,
"canListChildren"
:
false
,
"canModifyContent"
:
true
,
"canModifyContentRestriction"
:
true
,
"canModifyEditorContentRestriction"
:
true
,
"canModifyOwnerContentRestriction"
:
true
,
"canModifyLabels"
:
true
,
"canMoveChildrenWithinDrive"
:
false
,
"canMoveItemIntoTeamDrive"
:
true
,
"canMoveItemOutOfDrive"
:
true
,
"canMoveItemWithinDrive"
:
true
,
"canReadLabels"
:
true
,
"canReadRevisions"
:
true
,
"canRemoveChildren"
:
false
,
"canRemoveContentRestriction"
:
false
,
"canRemoveMyDriveParent"
:
true
,
"canRename"
:
true
,
"canShare"
:
true
,
"canTrash"
:
true
,
"canUntrash"
:
true
}
}
```


## Scenarios for sharing Drive resources

There are five different types of sharing scenarios:

- To share a file in My Drive, the user must have
role=writer
or
role=owner
.
If the
writersCanShare
boolean value is set to
false
for the file, the user must have
role=owner
.
If the user with
role=writer
has temporary access governed by an
expiration date and time, they can't share the file. For more
information, see
Set an expiration date to limit item
access
.
To share a file in My Drive, the user must have
role=writer
or
role=owner
.

- If the
writersCanShare
boolean value is set to
false
for the file, the user must have
role=owner
.
If the
writersCanShare
boolean value is set to
false
for the file, the user must have
role=owner
.

- If the user with
role=writer
has temporary access governed by an
expiration date and time, they can't share the file. For more
information, see
Set an expiration date to limit item
access
.
If the user with
role=writer
has temporary access governed by an
expiration date and time, they can't share the file. For more
information, see
Set an expiration date to limit item
access
.

- To share a folder in My Drive, the user must have
role=writer
or
role=owner
.
If the
writersCanShare
boolean value is set to
false
for the file,
the user must have the more permissive
role=owner
.
Temporary access (governed by an expiration date and time) is only
allowed on folders with
role=reader
. For more information, see
see
Set an expiration date to limit item access
.
To share a folder in My Drive, the user must have
role=writer
or
role=owner
.

- If the
writersCanShare
boolean value is set to
false
for the file,
the user must have the more permissive
role=owner
.
If the
writersCanShare
boolean value is set to
false
for the file,
the user must have the more permissive
role=owner
.

- Temporary access (governed by an expiration date and time) is only
allowed on folders with
role=reader
. For more information, see
see
Set an expiration date to limit item access
.
Temporary access (governed by an expiration date and time) is only
allowed on folders with
role=reader
. For more information, see
see
Set an expiration date to limit item access
.

- To share a file in a shared drive, the user must have
role=writer
,
role=fileOrganizer
, or
role=organizer
.
The
writersCanShare
setting doesn't apply to items in shared drives.
It's treated as if it's always set to
true
.
To share a file in a shared drive, the user must have
role=writer
,
role=fileOrganizer
, or
role=organizer
.

- The
writersCanShare
setting doesn't apply to items in shared drives.
It's treated as if it's always set to
true
.
- To share a folder in a shared drive, the user must have
role=organizer
.
If the
sharingFoldersRequiresOrganizerPermission
restriction on a shared drive is set to
false
, users with
role=fileOrganizer
can share folders in that shared drive.
To share a folder in a shared drive, the user must have
role=organizer
.

- If the
sharingFoldersRequiresOrganizerPermission
restriction on a shared drive is set to
false
, users with
role=fileOrganizer
can share folders in that shared drive.
- To manage shared drive membership, the user must have
role=organizer
. Only
users and groups can be members of shared drives.
To manage shared drive membership, the user must have
role=organizer
. Only
users and groups can be members of shared drives.


## Use the fields parameter

If you want to specify the fields to return in the response, you can set the
fields
system
parameter
with any method of the
permissions
resource. If you omit the
fields
parameter, the server returns a default set of fields specific to the method.
For example, the
list
method returns
only the
id
,
type
,
kind
, and
role
fields for each file. To return
different fields, see
Return specific fields
.


## Create a permission

The following two fields are necessary when creating a permission:

- type
: The
type
identifies the permission scope (
user
,
group
,
domain
, or
anyone
). A
permission with
type=user
applies to a specific user whereas a permission
with
type=domain
applies to everyone in a specific domain.
type
: The
type
identifies the permission scope (
user
,
group
,
domain
, or
anyone
). A
permission with
type=user
applies to a specific user whereas a permission
with
type=domain
applies to everyone in a specific domain.

- role
: The
role
field identifies operations the
type
can perform. For example, a
permission with
type=user
and
role=reader
grants a specific user
read-only access to the file or folder. Or, a permission with
type=domain
and
role=commenter
lets everyone in the domain add comments to a file. For
a complete list of roles and the operations permitted by each, refer to
Roles and permissions
.
role
: The
role
field identifies operations the
type
can perform. For example, a
permission with
type=user
and
role=reader
grants a specific user
read-only access to the file or folder. Or, a permission with
type=domain
and
role=commenter
lets everyone in the domain add comments to a file. For
a complete list of roles and the operations permitted by each, refer to
Roles and permissions
.

When you create a permission where
type=user
or
type=group
, you must also
provide an
emailAddress
to tie the specific user or group to the permission.

When you create a permission where
type=domain
, you must also provide a
domain
to tie a
specific domain to the permission.

To create a permission:

- Use the
create
method on the
permissions
resource with the
fileId
path parameter for the associated file or folder.
- In the request body, specify the
type
and
role
.
- If
type=user
or
type=group
, provide an
emailAddress
. If
type=domain
,
provide a
domain
.
The following code sample shows how to create a permission. The response returns an instance of a
permissions
resource, including the assigned
permissionId
.


```bash
POST https://www.googleapis.com/drive/v3/files/
FILE_ID
/permissions
```


```
{
"requests"
:
[
{
"type"
:
"user"
,
"role"
:
"commenter"
,
"emailAddress"
:
"alex@altostrat.com"
}
]
}
```


```
{
"kind"
:
"drive#permission"
,
"id"
:
"
PERMISSION_ID
"
,
"type"
:
"user"
,
"role"
:
"commenter"
}
```


### Use target audiences

Target audiences are groups of people—such as departments or teams—that you can
recommend for users to share their items with. You can encourage users to share
items with a more specific or limited audience rather than your entire
organization. Target audiences can help you improve the security and privacy of
your data, and make it easier for users to share appropriately. For more
information, see
About target
audiences
.

To use target audiences:

- In the Google Admin console, go to Menu
menu
>
Directory
>
Target audiences
.
Go to Target audiences
You must be signed in using an account with
super administrator
privileges for this task.
In the Google Admin console, go to Menu
menu
>
Directory
>
Target audiences
.

Go to Target audiences

You must be signed in using an account with
super administrator
privileges for this task.

- In the
Target audiences list
, click the name of the target audience. To
create a target audience, see
Create a target
audience
In the
Target audiences list
, click the name of the target audience. To
create a target audience, see
Create a target
audience

- Copy the unique ID from the target audience URL:
https://admin.google.com/ac/targetaudiences/
ID
.
Copy the unique ID from the target audience URL:
https://admin.google.com/ac/targetaudiences/
ID
.

- Create a permission
with
type=domain
, and set the
domain
field to
ID
.audience.googledomains.com
.
Create a permission
with
type=domain
, and set the
domain
field to
ID
.audience.googledomains.com
.

To view how users interact with target audiences, see
User experience for link
sharing
.


## Get a permission

To get a permission, use the
get
method
on the
permissions
resource with the
fileId
and
permissionId
path parameters. If you don't know the permission
ID, you can
list all permissions
using the
list
method.

The following code sample shows how to get a permission by ID. The response returns an instance of a
permissions
resource.


```bash
GET https://www.googleapis.com/drive/v3/files/
FILE_ID
/permissions
PERMISSION_ID
```


```
{
"kind"
:
"drive#permissionList"
,
"permissions"
:
[
{
"kind"
:
"drive#permission"
,
"id"
:
"
PERMISSION_ID
"
,
"type"
:
"user"
,
"role"
:
"commenter"
}
]
}
```


## List all permissions

To list permissions for a file, folder, or shared drive, use the
list
method on the
permissions
resource with the
fileId
path parameter.

Pass the following
query
parameters
to customize
pagination of, or to filter, permissions:

- pageSize
: The maximum number of permissions to return per page. If not set
for files in a shared drive, at most 100 results are returned. If not set
for files that aren't in a shared drive, the entire list is returned.
pageSize
: The maximum number of permissions to return per page. If not set
for files in a shared drive, at most 100 results are returned. If not set
for files that aren't in a shared drive, the entire list is returned.

- pageToken
: A page token, received from a previous list call. Provide this
token to retrieve the subsequent page.
pageToken
: A page token, received from a previous list call. Provide this
token to retrieve the subsequent page.

- supportsAllDrives
: Whether the requesting app supports both My Drives and
shared drives.
supportsAllDrives
: Whether the requesting app supports both My Drives and
shared drives.

- useDomainAdminAccess
: Set to
true
to issue the request as a domain
administrator. If the
fileId
parameter refers to a shared drive and the
requester is an administrator of the domain to which the shared drive
belongs. For more information, see
Manage shared drives as domain
administrators
.
useDomainAdminAccess
: Set to
true
to issue the request as a domain
administrator. If the
fileId
parameter refers to a shared drive and the
requester is an administrator of the domain to which the shared drive
belongs. For more information, see
Manage shared drives as domain
administrators
.

- includePermissionsForView
: The additional view's permissions to include in
the response. Only
published
is supported.
includePermissionsForView
: The additional view's permissions to include in
the response. Only
published
is supported.

The following code sample shows how to get all permissions. The response returns a list of permissions for a file, folder, or shared drive.


```bash
GET https://www.googleapis.com/drive/v3/files/
FILE_ID
/permissions
```


```
{
"kind"
:
"drive#permissionList"
,
"permissions"
:
[
{
"id"
:
"
PERMISSION_ID
"
,
"type"
:
"user"
,
"kind"
:
"drive#permission"
,
"role"
:
"commenter"
}
]
}
```


## Update permissions

To update permissions on a file or folder, you can change the assigned role. For
more information on finding the role source, see
Determine the role
source
.

- Call the
update
method on the
permissions
resource with the
fileId
path parameter set to the associated file, folder, or shared drive and the
permissionId
path parameter set to the permission to change. To find the
permissionId
, use the
list
method
on the
permissions
resource with the
fileId
path parameter.
Call the
update
method on the
permissions
resource with the
fileId
path parameter set to the associated file, folder, or shared drive and the
permissionId
path parameter set to the permission to change. To find the
permissionId
, use the
list
method
on the
permissions
resource with the
fileId
path parameter.

- In the request, identify the new
role
.
In the request, identify the new
role
.

You can grant permissions on individual files or folders in a shared drive even
if the user or group is already a member. For example, Alex has
role=commenter
as part of their membership to a shared drive. However, your app can grant Alex
role=writer
for a file in a shared drive. In this case, because the new role
is more permissive than the role granted through their membership, the new
permission becomes the
effective role
for the file or folder.

You can apply updates through patch semantics, meaning you can make partial
modifications to a resource. You must explicitly set the fields that you intend
to modify in your request. Any fields not included in the request retain their
existing values. For more information, see
Working with partial resources
.

The following code sample shows how to change permissions on a file or folder from
commenter
to
writer
. The response returns an instance of a
permissions
resource.


```
PATCH https://www.googleapis.com/drive/v3/files/
FILE_ID
/permissions/
PERMISSION_ID
```


```
{
  "role": "writer"
}
```


```
{
"kind"
:
"drive#permission"
,
"id"
:
"
PERMISSION_ID
"
,
"type"
:
"user"
,
"role"
:
"writer"
}
```


### Determine the role source

To change the role on a file or folder, you must know the source of the role.
For shared drives, the source of a role can be based on membership to the shared
drive, the role on a folder, or the role on a file.

To determine the role source for a shared drive, or items within that drive,
call the
get
method on the
permissions
resource with the
fileId
and
permissionId
path parameters, and the
fields
parameter set to the
permissionDetails
field.

To find the
permissionId
, use the
list
method on the
permissions
resource with the
fileId
path parameter. To fetch the
permissionDetails
field on the
list
request, set the
fields
parameter to
permissions/permissionDetails
.

This field enumerates all inherited and direct file permissions for the user,
group, or domain.

The following code sample shows how to determine the role source. The response returns the
permissionDetails
of a
permissions
resource. The
inheritedFrom
field provides the ID of the item from which the permission is inherited.


```bash
GET https://www.googleapis.com/drive/v3/files/
FILE_ID
/permissions/
PERMISSION_ID
?fields=permissionDetails&supportsAllDrives=true
```


```
{
  "permissionDetails": [
    {
      "permissionType": "member",
      "role": "commenter",
      "inheritedFrom": "
INHERITED_FROM_ID
",
      "inherited": true
    },
    {
      "permissionType": "file",
      "role": "writer",
      "inherited": false
    }
  ]
}
```


## Update multiple permissions with batch requests

We strongly recommend using
batch
requests
to modify multiple
permissions.

The following is an example of performing a batch permission modification with a
client library.


### Java


```
import
com.google.api.client.googleapis.batch.BatchRequest
;
import
com.google.api.client.googleapis.batch.json.JsonBatchCallback
;
import
com.google.api.client.googleapis.json.GoogleJsonError
;
import
com.google.api.client.googleapis.json.GoogleJsonResponseException
;
import
com.google.api.client.http.HttpHeaders
;
import
com.google.api.client.http.HttpRequestInitializer
;
import
com.google.api.client.http.javanet.NetHttpTransport
;
import
com.google.api.client.json.gson.GsonFactory
;
import
com.google.api.services.drive.Drive
;
import
com.google.api.services.drive.DriveScopes
;
import
com.google.api.services.drive.model.Permission
;
import
com.google.auth.http.HttpCredentialsAdapter
;
import
com.google.auth.oauth2.GoogleCredentials
;
import
java.io.IOException
;
import
java.util.ArrayList
;
import
java.util.Arrays
;
import
java.util.List
;
/* Class to demonstrate use-case of modify permissions. */
public
class
ShareFile
{
/**
* Batch permission modification.
* realFileId file Id.
* realUser User Id.
* realDomain Domain of the user ID.
*
* @return list of modified permissions if successful, {@code null} otherwise.
* @throws IOException if service account credentials file not found.
*/
public
static
List<String>
shareFile
(
String
realFileId
,
String
realUser
,
String
realDomain
)
throws
IOException
{
/* Load pre-authorized user credentials from the environment.
TODO(developer) - See https://developers.google.com/identity for
guides on implementing OAuth2 for your application.application*/
GoogleCredentials
credentials
=
GoogleCredentials
.
getApplicationDefault
()
.
createScoped
(
Arrays
.
asList
(
DriveScopes
.
DRIVE_FILE
));
HttpRequestInitializer
requestInitializer
=
new
HttpCredentialsAdapter
(
credentials
);
// Build a new authorized API client service.
Drive
service
=
new
Drive
.
Builder
(
new
NetHttpTransport
(),
GsonFactory
.
getDefaultInstance
(),
requestInitializer
)
.
setApplicationName
(
"Drive samples"
)
.
build
();
final
List<String>
ids
=
new
ArrayList<String>
();
JsonBatchCallback<Permission>
callback
=
new
JsonBatchCallback<Permission>
()
{
@Override
public
void
onFailure
(
GoogleJsonError
e
,
HttpHeaders
responseHeaders
)
throws
IOException
{
// Handle error
System
.
err
.
println
(
e
.
getMessage
());
}
@Override
public
void
onSuccess
(
Permission
permission
,
HttpHeaders
responseHeaders
)
throws
IOException
{
System
.
out
.
println
(
"Permission ID: "
+
permission
.
getId
());
ids
.
add
(
permission
.
getId
());
}
};
BatchRequest
batch
=
service
.
batch
();
Permission
userPermission
=
new
Permission
()
.
setType
(
"user"
)
.
setRole
(
"writer"
);
userPermission
.
setEmailAddress
(
realUser
);
try
{
service
.
permissions
().
create
(
realFileId
,
userPermission
)
.
setFields
(
"id"
)
.
queue
(
batch
,
callback
);
Permission
domainPermission
=
new
Permission
()
.
setType
(
"domain"
)
.
setRole
(
"reader"
);
domainPermission
.
setDomain
(
realDomain
);
service
.
permissions
().
create
(
realFileId
,
domainPermission
)
.
setFields
(
"id"
)
.
queue
(
batch
,
callback
);
batch
.
execute
();
return
ids
;
}
catch
(
GoogleJsonResponseException
e
)
{
// TODO(developer) - handle error appropriately
System
.
err
.
println
(
"Unable to modify permission: "
+
e
.
getDetails
());
throw
e
;
}
}
}
```


### Python


```
import
google.auth
from
googleapiclient.discovery
import
build
from
googleapiclient.errors
import
HttpError
def
share_file
(
real_file_id
,
real_user
,
real_domain
):
"""Batch permission modification.
Args:
real_file_id: file Id
real_user: User ID
real_domain: Domain of the user ID
Prints modified permissions
Load pre-authorized user credentials from the environment.
TODO(developer) - See https://developers.google.com/identity
for guides on implementing OAuth2 for the application.
"""
creds
,
_
=
google
.
auth
.
default
()
try
:
# create drive api client
service
=
build
(
"drive"
,
"v3"
,
credentials
=
creds
)
ids
=
[]
file_id
=
real_file_id
def
callback
(
request_id
,
response
,
exception
):
if
exception
:
# Handle error
print
(
exception
)
else
:
print
(
f
"Request_Id:
{
request_id
}
"
)
print
(
f
'Permission Id:
{
response
.
get
(
"id"
)
}
'
)
ids
.
append
(
response
.
get
(
"id"
))
# pylint: disable=maybe-no-member
batch
=
service
.
new_batch_http_request
(
callback
=
callback
)
user_permission
=
{
"type"
:
"user"
,
"role"
:
"writer"
,
"emailAddress"
:
"user@example.com"
,
}
batch
.
add
(
service
.
permissions
()
.
create
(
fileId
=
file_id
,
body
=
user_permission
,
fields
=
"id"
,
)
)
domain_permission
=
{
"type"
:
"domain"
,
"role"
:
"reader"
,
"domain"
:
"example.com"
,
}
domain_permission
[
"domain"
]
=
real_domain
batch
.
add
(
service
.
permissions
()
.
create
(
fileId
=
file_id
,
body
=
domain_permission
,
fields
=
"id"
,
)
)
batch
.
execute
()
except
HttpError
as
error
:
print
(
f
"An error occurred:
{
error
}
"
)
ids
=
None
return
ids
if
__name__
==
"__main__"
:
share_file
(
real_file_id
=
"1dUiRSoAQKkM3a4nTPeNQWgiuau1KdQ_l"
,
real_user
=
"gduser1@workspacesamples.dev"
,
real_domain
=
"workspacesamples.dev"
,
)
```


### Node.js


```
import
{
GoogleAuth
}
from
'google-auth-library'
;
import
{
google
}
from
'googleapis'
;
/**
* Shares a file with a user and a domain.
* @param {string} fileId The ID of the file to share.
* @param {string} targetUserEmail The email address of the user to share with.
* @param {string} targetDomainName The domain to share with.
* @return {Promise<Array<string>>} A promise that resolves to an array of permission IDs.
*/
async
function
shareFile
(
fileId
,
targetUserEmail
,
targetDomainName
)
{
// Authenticate with Google and get an authorized client.
// TODO (developer): Use an appropriate auth mechanism for your app.
const
auth
=
new
GoogleAuth
({
scopes
:
'https://www.googleapis.com/auth/drive'
,
});
// Create a new Drive API client (v3).
const
service
=
google
.
drive
({
version
:
'v3'
,
auth
});
/** @type {Array<string>} */
const
permissionIds
=
[];
// The permissions to create.
const
permissions
=
[
{
type
:
'user'
,
role
:
'writer'
,
emailAddress
:
targetUserEmail
,
// e.g., 'user@partner.com'
},
{
type
:
'domain'
,
role
:
'writer'
,
domain
:
targetDomainName
,
// e.g., 'example.com'
},
];
// Iterate through the permissions and create them one by one.
for
(
const
permission
of
permissions
)
{
const
result
=
await
service
.
permissions
.
create
({
requestBody
:
permission
,
fileId
,
fields
:
'id'
,
});
if
(
result
.
data
.
id
)
{
permissionIds
.
push
(
result
.
data
.
id
);
console
.
log
(
`Inserted permission id:
${
result
.
data
.
id
}
`
);
}
else
{
throw
new
Error
(
'Failed to create permission'
);
}
}
return
permissionIds
;
}
```


### PHP


```
<
?php
use Google\Client;
use Google\Service\Drive;
function shareFile()
{
try {
$client = new Client();
$client->useApplicationDefaultCredentials();
$client->addScope(Drive::DRIVE);
$driveService = new Drive($client);
$realFileId = readline("Enter File Id: ");
$realUser = readline("Enter user email address: ");
$realDomain = readline("Enter domain name: ");
$ids = array();
$fileId = '1sTWaJ_j7PkjzaBWtNc3IzovK5hQf21FbOw9yLeeLPNQ';
$fileId = $realFileId;
$driveService->getClient()->setUseBatch(true);
try {
$batch = $driveService->createBatch();
$userPermission = new Drive\Permission(array(
'type' => 'user',
'role' => 'writer',
'emailAddress' => 'user@example.com'
));
$userPermission['emailAddress'] = $realUser;
$request = $driveService->permissions->create(
$fileId, $userPermission, array('fields' => 'id'));
$batch->add($request, 'user');
$domainPermission = new Drive\Permission(array(
'type' => 'domain',
'role' => 'reader',
'domain' => 'example.com'
));
$userPermission['domain'] = $realDomain;
$request = $driveService->permissions->create(
$fileId, $domainPermission, array('fields' => 'id'));
$batch->add($request, 'domain');
$results = $batch->execute();
foreach ($results as $result) {
if ($result instanceof Google_Service_Exception) {
// Handle error
printf($result);
} else {
printf("Permission ID: %s\n", $result->id);
array_push($ids, $result->id);
}
}
} finally {
$driveService->getClient()->setUseBatch(false);
}
return $ids;
} catch(Exception $e) {
echo "Error Message: ".$e;
}
}
```


### .NET


```
using
Google.Apis.Auth.OAuth2
;
using
Google.Apis.Drive.v3
;
using
Google.Apis.Drive.v3.Data
;
using
Google.Apis.Requests
;
using
Google.Apis.Services
;
namespace
DriveV3Snippets
{
// Class to demonstrate use-case of Drive modify permissions.
public
class
ShareFile
{
/// <summary>
/// Batch permission modification.
/// </summary>
/// <param name="realFileId">File id.</param>
/// <param name="realUser">User id.</param>
/// <param name="realDomain">Domain id.</param>
/// <returns>list of modified permissions, null otherwise.</returns>
public
static
IList<String>
DriveShareFile
(
string
realFileId
,
string
realUser
,
string
realDomain
)
{
try
{
/* Load pre-authorized user credentials from the environment.
TODO(developer) - See https://developers.google.com/identity for
guides on implementing OAuth2 for your application. */
GoogleCredential
credential
=
GoogleCredential
.
GetApplicationDefault
()
.
CreateScoped
(
DriveService
.
Scope
.
Drive
);
// Create Drive API service.
var
service
=
new
DriveService
(
new
BaseClientService
.
Initializer
{
HttpClientInitializer
=
credential
,
ApplicationName
=
"Drive API Snippets"
});
var
ids
=
new
List<String>
();
var
batch
=
new
BatchRequest
(
service
);
BatchRequest
.
OnResponse<Permission>
callback
=
delegate
(
Permission
permission
,
RequestError
error
,
int
index
,
HttpResponseMessage
message
)
{
if
(
error
!=
null
)
{
// Handle error
Console
.
WriteLine
(
error
.
Message
);
}
else
{
Console
.
WriteLine
(
"Permission ID: "
+
permission
.
Id
);
}
};
Permission
userPermission
=
new
Permission
()
{
Type
=
"user"
,
Role
=
"writer"
,
EmailAddress
=
realUser
};
var
request
=
service
.
Permissions
.
Create
(
userPermission
,
realFileId
);
request
.
Fields
=
"id"
;
batch
.
Queue
(
request
,
callback
);
Permission
domainPermission
=
new
Permission
()
{
Type
=
"domain"
,
Role
=
"reader"
,
Domain
=
realDomain
};
request
=
service
.
Permissions
.
Create
(
domainPermission
,
realFileId
);
request
.
Fields
=
"id"
;
batch
.
Queue
(
request
,
callback
);
var
task
=
batch
.
ExecuteAsync
();
task
.
Wait
();
return
ids
;
}
catch
(
Exception
e
)
{
// TODO(developer) - handle error appropriately
if
(
e
is
AggregateException
)
{
Console
.
WriteLine
(
"Credential Not found"
);
}
else
{
throw
;
}
}
return
null
;
}
}
}
```


## Delete a permission

To revoke access to a file or folder, call the
delete
method on the
permissions
resource with the
fileId
and
the
permissionId
path parameters set to delete the permission.

Inherited permissions cannot be revoked. Update or delete the permission on the
parent folder instead. Deleting a permission on a folder also revokes any
equivalent access on child items.

Reducing permissions compared to a parent requires using the
limited access
setting
.

Note that removing a user's access from a parent item only revokes permissions
inherited from the parent. If a user was granted permissions on a child file or
folder directly, their access persists. To make sure all child items match the
parent's permissions, you must identify and remove any direct permissions
granted to the user on those child items.

The following code sample shows how to revoke access by deleting a
permissionId
. If successful, the response body is an empty JSON object. To confirm the permission is removed, use the
list
method on the
permissions
resource with the
fileId
path parameter.


```
DELETE https://www.googleapis.com/drive/v3/files/
FILE_ID
/permissions/
PERMISSION_ID
```


## Set an expiration date to limit item access

When you're working with people on a sensitive project, you might want to
restrict their access to certain items in Drive after a period of
time. For files and folders, you can set an expiration date to
limit or remove access to that item.

To set the expiration date:

- Use the
create
method on the
permissions
resource and set the
expirationTime
field (along with the other required fields). For more information, see
Create a permission
.
Use the
create
method on the
permissions
resource and set the
expirationTime
field (along with the other required fields). For more information, see
Create a permission
.

- Use the
update
method on the
permissions
resource and set the
expirationTime
field (along with the
other required fields). For more information, see
Update
permissions
.
Use the
update
method on the
permissions
resource and set the
expirationTime
field (along with the
other required fields). For more information, see
Update
permissions
.

The
expirationTime
field denotes when the permission expires using
RFC 3339
date-time
. Expiration times have
the following restrictions:

- They can only be set on user and group permissions.
- Time must be in the future.
- The time cannot be more than one year in the future.
- Only the
reader
role is eligible for expiring access on a folder.
For more information about expiration date, see the following articles:

- Set an expiration date for file access
- Add an expiration date

## Related topics

- Manage pending access proposals
- Manage folders with limited and expansive access
- Transfer file ownership
- Protect file content
- Access link-shared drive files using resource keys
- Roles and permissions
Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2026-05-07 UTC.


---

# Upload file data Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/guides/manage-uploads

- Home
- Google Workspace
- Google Drive
- Guides
The Google Drive API lets you upload file data when you create or update a
File
. For information about how to create a
metadata-only file, such as a folder, see
Create metadata-only files
.

There are three types of uploads you can perform:

- Simple upload (
uploadType=media
)
: Use this upload type to transfer a
small media file (5 MB or less) without supplying metadata. To perform a
simple upload, refer to
Perform a simple upload
.
Simple upload (
uploadType=media
)
: Use this upload type to transfer a
small media file (5 MB or less) without supplying metadata. To perform a
simple upload, refer to
Perform a simple upload
.

- Multipart upload (
uploadType=multipart
)
: "Use this upload type to
transfer a small file (5 MB or less) along with metadata that describes the
file, in a single request. To perform a multipart upload, refer to
Perform
a multipart upload
.
Multipart upload (
uploadType=multipart
)
: "Use this upload type to
transfer a small file (5 MB or less) along with metadata that describes the
file, in a single request. To perform a multipart upload, refer to
Perform
a multipart upload
.

- Resumable upload (
uploadType=resumable
)
: Use this upload type for
large files (greater than 5 MB) and when there's a high chance of network
interruption, such as when creating a file from a mobile app. Resumable
uploads are also a good choice for most applications because they also work
for small files at a minimal cost of one additional HTTP request per upload.
To perform a resumable upload, refer to
Perform a resumable
upload
.
Resumable upload (
uploadType=resumable
)
: Use this upload type for
large files (greater than 5 MB) and when there's a high chance of network
interruption, such as when creating a file from a mobile app. Resumable
uploads are also a good choice for most applications because they also work
for small files at a minimal cost of one additional HTTP request per upload.
To perform a resumable upload, refer to
Perform a resumable
upload
.

The Google API client libraries implement at least one of these types of
uploads. Refer to the
client library
documentation
for additional details about how to
use each of the types.


## Use
PATCH
vs.
PUT

As a refresher, the HTTP verb
PATCH
supports a partial file resource update
whereas the HTTP verb
PUT
supports full resource replacement. Note that
PUT
can introduce breaking changes when adding a new field to an existing resource.

When uploading a file resource, use the following guidelines:

- Use the HTTP verb documented on the API reference for the initial request of
a resumable upload or for the only request of a simple or multipart upload.
- Use
PUT
for all subsequent requests for a resumable upload once the
request has started. These requests are uploading content no matter the
method being called.

## Perform a simple upload

To perform a simple upload, use the
create
method on the
files
resource with
uploadType=media
.

The following shows how to perform a simple upload:


### HTTP

- Create a
POST
request to the method's /upload URI with the query
parameter of
uploadType=media
:
POST https://www.googleapis.com/upload/drive/v3/files?uploadType=media
Create a
POST
request to the method's /upload URI with the query
parameter of
uploadType=media
:

POST https://www.googleapis.com/upload/drive/v3/files?uploadType=media

- Add the file's data to the request body.
Add the file's data to the request body.

- Add these HTTP headers:
Content-Type
. Set to the MIME media type of the object being
uploaded.
Content-Length
. Set to the number of bytes you upload. If you use
chunked transfer encoding, this header is not required.
Add these HTTP headers:

- Content-Type
. Set to the MIME media type of the object being
uploaded.
- Content-Length
. Set to the number of bytes you upload. If you use
chunked transfer encoding, this header is not required.
- Send the request. If the request succeeds, the server returns the
HTTP
200 OK
status code along with the file's metadata. {HTTP}
Send the request. If the request succeeds, the server returns the
HTTP
200 OK
status code along with the file's metadata. {HTTP}

When you perform a simple upload, basic metadata is created and some attributes
are inferred from the file, such as the MIME type or
modifiedTime
. You can use
a simple upload in cases where you have small files and file metadata isn't
important.


## Perform a multipart upload

A multipart upload request lets you upload metadata and data in the same
request. Use this option if the data you send is small enough to upload again,
in its entirety, if the connection fails.

To perform a multipart upload, use the
create
method on the
files
resource with
uploadType=multipart
.

The following shows how to perform a multipart upload:


### Java


```
import
com.google.api.client.googleapis.json.GoogleJsonResponseException
;
import
com.google.api.client.http.FileContent
;
import
com.google.api.client.http.HttpRequestInitializer
;
import
com.google.api.client.http.javanet.NetHttpTransport
;
import
com.google.api.client.json.gson.GsonFactory
;
import
com.google.api.services.drive.Drive
;
import
com.google.api.services.drive.DriveScopes
;
import
com.google.api.services.drive.model.File
;
import
com.google.auth.http.HttpCredentialsAdapter
;
import
com.google.auth.oauth2.GoogleCredentials
;
import
java.io.IOException
;
import
java.util.Arrays
;
/* Class to demonstrate use of Drive insert file API */
public
class
UploadBasic
{
/**
* Upload new file.
*
* @return Inserted file metadata if successful, {@code null} otherwise.
* @throws IOException if service account credentials file not found.
*/
public
static
String
uploadBasic
()
throws
IOException
{
// Load pre-authorized user credentials from the environment.
// TODO(developer) - See https://developers.google.com/identity for
// guides on implementing OAuth2 for your application.
GoogleCredentials
credentials
=
GoogleCredentials
.
getApplicationDefault
()
.
createScoped
(
Arrays
.
asList
(
DriveScopes
.
DRIVE_FILE
));
HttpRequestInitializer
requestInitializer
=
new
HttpCredentialsAdapter
(
credentials
);
// Build a new authorized API client service.
Drive
service
=
new
Drive
.
Builder
(
new
NetHttpTransport
(),
GsonFactory
.
getDefaultInstance
(),
requestInitializer
)
.
setApplicationName
(
"Drive samples"
)
.
build
();
// Upload file photo.jpg on drive.
File
fileMetadata
=
new
File
();
fileMetadata
.
setName
(
"photo.jpg"
);
// File's content.
java
.
io
.
File
filePath
=
new
java
.
io
.
File
(
"files/photo.jpg"
);
// Specify media type and file-path for file.
FileContent
mediaContent
=
new
FileContent
(
"image/jpeg"
,
filePath
);
try
{
File
file
=
service
.
files
().
create
(
fileMetadata
,
mediaContent
)
.
setFields
(
"id"
)
.
execute
();
System
.
out
.
println
(
"File ID: "
+
file
.
getId
());
return
file
.
getId
();
}
catch
(
GoogleJsonResponseException
e
)
{
// TODO(developer) - handle error appropriately
System
.
err
.
println
(
"Unable to upload file: "
+
e
.
getDetails
());
throw
e
;
}
}
}
```


### Python


```
import
google.auth
from
googleapiclient.discovery
import
build
from
googleapiclient.errors
import
HttpError
from
googleapiclient.http
import
MediaFileUpload
def
upload_basic
():
"""Insert new file.
Returns : Id's of the file uploaded
Load pre-authorized user credentials from the environment.
TODO(developer) - See https://developers.google.com/identity
for guides on implementing OAuth2 for the application.
"""
creds
,
_
=
google
.
auth
.
default
()
try
:
# create drive api client
service
=
build
(
"drive"
,
"v3"
,
credentials
=
creds
)
file_metadata
=
{
"name"
:
"download.jpeg"
}
media
=
MediaFileUpload
(
"download.jpeg"
,
mimetype
=
"image/jpeg"
)
# pylint: disable=maybe-no-member
file
=
(
service
.
files
()
.
create
(
body
=
file_metadata
,
media_body
=
media
,
fields
=
"id"
)
.
execute
()
)
print
(
f
'File ID:
{
file
.
get
(
"id"
)
}
'
)
except
HttpError
as
error
:
print
(
f
"An error occurred:
{
error
}
"
)
file
=
None
return
file
.
get
(
"id"
)
if
__name__
==
"__main__"
:
upload_basic
()
```


### Node.js


```
import
fs
from
'node:fs'
;
import
{
GoogleAuth
}
from
'google-auth-library'
;
import
{
google
}
from
'googleapis'
;
/**
* Uploads a file to Google Drive.
* @return {Promise<string|null|undefined>} The ID of the uploaded file.
*/
async
function
uploadBasic
()
{
// Authenticate with Google and get an authorized client.
// TODO (developer): Use an appropriate auth mechanism for your app.
const
auth
=
new
GoogleAuth
({
scopes
:
'https://www.googleapis.com/auth/drive'
,
});
// Create a new Drive API client (v3).
const
service
=
google
.
drive
({
version
:
'v3'
,
auth
});
// The request body for the file to be uploaded.
const
requestBody
=
{
name
:
'photo.jpg'
,
fields
:
'id'
,
};
// The media content to be uploaded.
const
media
=
{
mimeType
:
'image/jpeg'
,
body
:
fs
.
createReadStream
(
'files/photo.jpg'
),
};
// Upload the file.
const
file
=
await
service
.
files
.
create
({
requestBody
,
media
,
});
// Print the ID of the uploaded file.
console
.
log
(
'File Id:'
,
file
.
data
.
id
);
return
file
.
data
.
id
;
}
```


### PHP


```
<
?php
use Google\Client;
use Google\Service\Drive;
# TODO - PHP client currently chokes on fetching start page token
function uploadBasic()
{
try {
$client = new Client();
$client->useApplicationDefaultCredentials();
$client->addScope(Drive::DRIVE);
$driveService = new Drive($client);
$fileMetadata = new Drive\DriveFile(array(
'name' => 'photo.jpg'));
$content = file_get_contents('../files/photo.jpg');
$file = $driveService->files->create($fileMetadata, array(
'data' => $content,
'mimeType' => 'image/jpeg',
'uploadType' => 'multipart',
'fields' => 'id'));
printf("File ID: %s\n", $file->id);
return $file->id;
} catch(Exception $e) {
echo "Error Message: ".$e;
}
}
```


### .NET


```
using
Google.Apis.Auth.OAuth2
;
using
Google.Apis.Drive.v3
;
using
Google.Apis.Services
;
namespace
DriveV3Snippets
{
// Class to demonstrate use of Drive insert file API
public
class
UploadBasic
{
/// <summary>
/// Upload new file.
/// </summary>
/// <param name="filePath">Image path to upload.</param>
/// <returns>Inserted file metadata if successful, null otherwise.</returns>
public
static
string
DriveUploadBasic
(
string
filePath
)
{
try
{
/* Load pre-authorized user credentials from the environment.
TODO(developer) - See https://developers.google.com/identity for
guides on implementing OAuth2 for your application. */
GoogleCredential
credential
=
GoogleCredential
.
GetApplicationDefault
()
.
CreateScoped
(
DriveService
.
Scope
.
Drive
);
// Create Drive API service.
var
service
=
new
DriveService
(
new
BaseClientService
.
Initializer
{
HttpClientInitializer
=
credential
,
ApplicationName
=
"Drive API Snippets"
});
// Upload file photo.jpg on drive.
var
fileMetadata
=
new
Google
.
Apis
.
Drive
.
v3
.
Data
.
File
()
{
Name
=
"photo.jpg"
};
FilesResource
.
CreateMediaUpload
request
;
// Create a new file on drive.
using
(
var
stream
=
new
FileStream
(
filePath
,
FileMode
.
Open
))
{
// Create a new file, with metadata and stream.
request
=
service
.
Files
.
Create
(
fileMetadata
,
stream
,
"image/jpeg"
);
request
.
Fields
=
"id"
;
request
.
Upload
();
}
var
file
=
request
.
ResponseBody
;
// Prints the uploaded file id.
Console
.
WriteLine
(
"File ID: "
+
file
.
Id
);
return
file
.
Id
;
}
catch
(
Exception
e
)
{
// TODO(developer) - handle error appropriately
if
(
e
is
AggregateException
)
{
Console
.
WriteLine
(
"Credential Not found"
);
}
else
if
(
e
is
FileNotFoundException
)
{
Console
.
WriteLine
(
"File not found"
);
}
else
{
throw
;
}
}
return
null
;
}
}
}
```

- Create a
POST
request to the method's /upload URI with the query
parameter of
uploadType=multipart
:
POST https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart
Create a
POST
request to the method's /upload URI with the query
parameter of
uploadType=multipart
:

POST https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart

- Create the body of the request. Format the body according to the
multipart/related content type
RFC 2387
,
which contains two parts:
Metadata. The metadata must come first and must have a
Content-Type
header set to
application/json;
charset=UTF-8
. Add the file's metadata
in JSON format.
Media. The media must come second and must have a
Content-Type
header
of any MIME type. Add the file's data to the media part.
Identify each part with a boundary string, preceded by two hyphens. In
addition, add two hyphens after the final boundary string.
Create the body of the request. Format the body according to the
multipart/related content type
RFC 2387
,
which contains two parts:

- Metadata. The metadata must come first and must have a
Content-Type
header set to
application/json;
charset=UTF-8
. Add the file's metadata
in JSON format.
- Media. The media must come second and must have a
Content-Type
header
of any MIME type. Add the file's data to the media part.
Identify each part with a boundary string, preceded by two hyphens. In
addition, add two hyphens after the final boundary string.

- Add these top-level HTTP headers:
Content-Type
. Set to
multipart/related
and include the boundary
string you're using to identify the different parts of the request. For
example:
Content-Type: multipart/related; boundary=foo_bar_baz
Content-Length
. Set to the total number of bytes in the request body.
Add these top-level HTTP headers:

- Content-Type
. Set to
multipart/related
and include the boundary
string you're using to identify the different parts of the request. For
example:
Content-Type: multipart/related; boundary=foo_bar_baz
- Content-Length
. Set to the total number of bytes in the request body.
- Send the request.
Send the request.

To create or update the metadata portion only, without the associated data,
send a
POST
or
PATCH
request to the standard resource endpoint:
https://www.googleapis.com/drive/v3/files
If the request succeeds,
the server returns the
HTTP 200 OK
status code along with the file's
metadata.

When creating files, they should specify a file extension in the file's
name
field. For example, when creating a photo JPEG file, you might specify something
like
"name": "photo.jpg"
in the metadata. Subsequent calls to the
get
method return the read-only
fileExtension
property containing the extension originally specified in the
name
field.


## Perform a resumable upload

A resumable upload lets you resume an upload operation after a communication
failure interrupts the flow of data. Because you don't have to restart large
file uploads from the start, resumable uploads can also reduce your bandwidth
usage if there's a network failure.

Resumable uploads are useful when your file sizes might vary greatly or when
there's a fixed time limit for requests (such as mobile OS background tasks and
certain App Engine requests). You might also use resumable uploads for
situations where you want to show an upload progress bar.

A resumable upload consists of several high-level steps:

- Send the initial request and retrieve the resumable session URI.
- Upload the data and monitor upload state.
- (optional) If the upload is disturbed, resume the upload.

### Send the initial request

To initiate a resumable upload, use the
create
method on the
files
resource with
uploadType=resumable
.

- Create a
POST
request to the method's /upload URI with the query
parameter of
uploadType=resumable
:
POST
https://www.googleapis.com/upload/drive/v3/files?uploadType=resumable
If the initiation request succeeds, the response includes a
200 OK
HTTP status code. In addition, it includes a
Location
header that
specifies the resumable session URI:
HTTP/1.1 200 OK
Location: https://www.googleapis.com/upload/drive/v3/files?uploadType=resumable&upload_id=xa298sd_sdlkj2
Content-Length: 0
Save the resumable session URI so you can upload the file data and query
the upload status. A resumable session URI expires after one week.
Create a
POST
request to the method's /upload URI with the query
parameter of
uploadType=resumable
:

POST
https://www.googleapis.com/upload/drive/v3/files?uploadType=resumable

If the initiation request succeeds, the response includes a
200 OK
HTTP status code. In addition, it includes a
Location
header that
specifies the resumable session URI:


```
HTTP/1.1 200 OK
Location: https://www.googleapis.com/upload/drive/v3/files?uploadType=resumable&upload_id=xa298sd_sdlkj2
Content-Length: 0
```

Save the resumable session URI so you can upload the file data and query
the upload status. A resumable session URI expires after one week.

- If you have metadata for the file, add the metadata to the request body
in JSON format. Otherwise, leave the request body empty.
If you have metadata for the file, add the metadata to the request body
in JSON format. Otherwise, leave the request body empty.

- Add these HTTP headers:
X-Upload-Content-Type
. Optional. Set to the MIME type of the file
data, which is transferred in subsequent requests. If the MIME type
of the data is not specified in the metadata or through this header,
the object is served as
application/octet-stream.
X-Upload-Content-Length
. Optional. Set to the number of bytes of
file data, which is transferred in subsequent requests.
Content-Type
. Required if you have metadata for the file. Set to
application/json;
charset=UTF-8
.
Content-Length
. Required unless you use chunked transfer encoding.
Set to the number of bytes in the body of this initial request.
- X-Upload-Content-Type
. Optional. Set to the MIME type of the file
data, which is transferred in subsequent requests. If the MIME type
of the data is not specified in the metadata or through this header,
the object is served as
application/octet-stream.
- X-Upload-Content-Length
. Optional. Set to the number of bytes of
file data, which is transferred in subsequent requests.
- Content-Type
. Required if you have metadata for the file. Set to
application/json;
charset=UTF-8
.
- Content-Length
. Required unless you use chunked transfer encoding.
Set to the number of bytes in the body of this initial request.
- Send the request. If the session initiation request succeeds, the
response includes a
200 OK HTTP
status code. In addition, the response
includes a
Location
header that specifies the resumable session URI.
Use the resumable session URI to upload the file data and query the
upload status. A resumable session URI expires after one week.
Send the request. If the session initiation request succeeds, the
response includes a
200 OK HTTP
status code. In addition, the response
includes a
Location
header that specifies the resumable session URI.
Use the resumable session URI to upload the file data and query the
upload status. A resumable session URI expires after one week.

- Copy and save the resumable session URL.
Copy and save the resumable session URL.

- Continue to
Upload the content
.
Continue to
Upload the content
.


### Upload the content

There are two ways to upload a file with a resumable session:

- Upload content in a single request
: Use this approach when the file can
be uploaded in one request, if there's no fixed time limit for any single
request, or you don't need to display an upload progress indicator. This
approach is best because it requires fewer requests and results in better
performance.
- Upload the content in multiple chunks
: Use this approach if you must
reduce the amount of data transferred in any single request. You might need
to reduce data transferred when there's a fixed time limit for individual
requests, as can be the case for certain classes of App Engine requests.
This approach is also useful if you must provide a customized indicator to
show the upload progress.
Upload the content in multiple chunks
: Use this approach if you must
reduce the amount of data transferred in any single request. You might need
to reduce data transferred when there's a fixed time limit for individual
requests, as can be the case for certain classes of App Engine requests.
This approach is also useful if you must provide a customized indicator to
show the upload progress.


### HTTP - single request

- Create a
PUT
request to the resumable session URI.
- Add a Content-Length HTTP header, set to the number of bytes in the file.
- Send the request. If the upload request is interrupted, or if you receive a
5xx
response, follow the procedure in
Resume an interrupted upload
.

### HTTP - multiple requests

Create a
PUT
request to the resumable session URI.

- Add the chunk's data to the request body. Create chunks in multiples of
256 KB (256 x 1024 bytes) in size, except for the final chunk that completes
the upload. Keep the chunk size as large as possible so that the upload is
efficient.
Add the chunk's data to the request body. Create chunks in multiples of
256 KB (256 x 1024 bytes) in size, except for the final chunk that completes
the upload. Keep the chunk size as large as possible so that the upload is
efficient.

- Add these HTTP headers:
Content-Length
. Set to the number of bytes in the current chunk.
Content-Range
. Set to show which bytes in the file you upload. For
example,
Content-Range: bytes 0-524287/2000000
shows that you upload the
first 524,288 bytes (256 x 1024 x 2) in a 2,000,000 byte file.
- Content-Length
. Set to the number of bytes in the current chunk.
- Content-Range
. Set to show which bytes in the file you upload. For
example,
Content-Range: bytes 0-524287/2000000
shows that you upload the
first 524,288 bytes (256 x 1024 x 2) in a 2,000,000 byte file.
- Send the request, and process the response. If the upload request is
interrupted, or if you receive a
5xx
response, follow the procedure in
Resume an interrupted upload
.
Send the request, and process the response. If the upload request is
interrupted, or if you receive a
5xx
response, follow the procedure in
Resume an interrupted upload
.

- Repeat steps 1 through 4 for each chunk that remains in the file. Use the
Range
header in the response to determine where to start the next chunk. 
Don't assume that the server received all bytes sent in the previous request.
Repeat steps 1 through 4 for each chunk that remains in the file. Use the
Range
header in the response to determine where to start the next chunk. 
Don't assume that the server received all bytes sent in the previous request.

When the entire file upload is complete, you receive a
200 OK
or
201 Created
response, along with any metadata associated with the resource.


### Resume an interrupted upload

If an upload request is terminated before a response, or if you receive a
503
Service Unavailable
response, then you must resume the interrupted upload.

- To request the upload status, create an empty
PUT
request to the
resumable session URI.
To request the upload status, create an empty
PUT
request to the
resumable session URI.

- Add a
Content-Range
header to indicate that the current position in the
file is unknown. For example, set the
Content-Range
to
*/2000000
if your
total file length is 2,000,000 bytes. If you don't know the full size of the
file, set the
Content-Range
to
*/*
.
Add a
Content-Range
header to indicate that the current position in the
file is unknown. For example, set the
Content-Range
to
*/2000000
if your
total file length is 2,000,000 bytes. If you don't know the full size of the
file, set the
Content-Range
to
*/*
.

- Process the response:
A
200 OK
or
201 Created
response indicates that the upload was
completed, and no further action is necessary.
A
308 Resume Incomplete
response indicates that you must continue
to upload the file.
A
404 Not Found
response indicates the upload session has expired and
the upload must be restarted from the beginning.
Process the response:

- A
200 OK
or
201 Created
response indicates that the upload was
completed, and no further action is necessary.
- A
308 Resume Incomplete
response indicates that you must continue
to upload the file.
- A
404 Not Found
response indicates the upload session has expired and
the upload must be restarted from the beginning.
- If you received a
308 Resume Incomplete
response, process the
Range
header of the response to determine which bytes the server has received. If the
response doesn't have a
Range
header, no bytes have been received.
For example, a
Range
header of
bytes=0-42
indicates that the first
43 bytes of the file were received and that the next chunk to upload
would start with byte 44.
If you received a
308 Resume Incomplete
response, process the
Range
header of the response to determine which bytes the server has received. If the
response doesn't have a
Range
header, no bytes have been received.
For example, a
Range
header of
bytes=0-42
indicates that the first
43 bytes of the file were received and that the next chunk to upload
would start with byte 44.

- Now that you know where to resume the upload, continue to upload the file
beginning with the next byte. Include a
Content-Range
header to indicate which portion of the file you send. For
example,
Content-Range: bytes 43-1999999
indicates that you
send bytes 44 through 2,000,000.
Now that you know where to resume the upload, continue to upload the file
beginning with the next byte. Include a
Content-Range
header to indicate which portion of the file you send. For
example,
Content-Range: bytes 43-1999999
indicates that you
send bytes 44 through 2,000,000.


## Handle media upload errors

When you upload media, follow these best practices to handle errors:

- For
5xx
errors, resume or retry uploads that fail due to connection
interruptions. For further information on handling
5xx
errors, refer to
500, 502, 503, 504 errors
.
- For
403 rate limit
errors, retry the upload. For further information about
handling
403 rate limit
errors, refer to
403 error:
rateLimitExceeded
.
- For any
4xx
errors (including
403
) during a resumable upload, restart
the upload. These errors indicate the upload session has expired and must be
restarted by
requesting a new session URI
. Upload sessions
also expire after one week of inactivity.

## Import to Google Docs types

When you create a file in Drive, you might want to convert the
file into a Google Workspace file type, such as Google Docs or
Sheets. For example, maybe you want to transform a document from
your favorite word processor into a Docs to take advantage of its
features.

To convert a file to a specific Google Workspace file type, specify the
Google Workspace
mimeType
when creating the file.

The following shows how to convert a CSV file to a Google Workspace sheet:


```
import
com.google.api.client.googleapis.json.GoogleJsonResponseException
;
import
com.google.api.client.http.FileContent
;
import
com.google.api.client.http.HttpRequestInitializer
;
import
com.google.api.client.http.javanet.NetHttpTransport
;
import
com.google.api.client.json.gson.GsonFactory
;
import
com.google.api.services.drive.Drive
;
import
com.google.api.services.drive.DriveScopes
;
import
com.google.api.services.drive.model.File
;
import
com.google.auth.http.HttpCredentialsAdapter
;
import
com.google.auth.oauth2.GoogleCredentials
;
import
java.io.IOException
;
import
java.util.Arrays
;
/* Class to demonstrate Drive's upload with conversion use-case. */
public
class
UploadWithConversion
{
/**
* Upload file with conversion.
*
* @return Inserted file id if successful, {@code null} otherwise.
* @throws IOException if service account credentials file not found.
*/
public
static
String
uploadWithConversion
()
throws
IOException
{
// Load pre-authorized user credentials from the environment.
// TODO(developer) - See https://developers.google.com/identity for
// guides on implementing OAuth2 for your application.
GoogleCredentials
credentials
=
GoogleCredentials
.
getApplicationDefault
()
.
createScoped
(
Arrays
.
asList
(
DriveScopes
.
DRIVE_FILE
));
HttpRequestInitializer
requestInitializer
=
new
HttpCredentialsAdapter
(
credentials
);
// Build a new authorized API client service.
Drive
service
=
new
Drive
.
Builder
(
new
NetHttpTransport
(),
GsonFactory
.
getDefaultInstance
(),
requestInitializer
)
.
setApplicationName
(
"Drive samples"
)
.
build
();
// File's metadata.
File
fileMetadata
=
new
File
();
fileMetadata
.
setName
(
"My Report"
);
fileMetadata
.
setMimeType
(
"application/vnd.google-apps.spreadsheet"
);
java
.
io
.
File
filePath
=
new
java
.
io
.
File
(
"files/report.csv"
);
FileContent
mediaContent
=
new
FileContent
(
"text/csv"
,
filePath
);
try
{
File
file
=
service
.
files
().
create
(
fileMetadata
,
mediaContent
)
.
setFields
(
"id"
)
.
execute
();
System
.
out
.
println
(
"File ID: "
+
file
.
getId
());
return
file
.
getId
();
}
catch
(
GoogleJsonResponseException
e
)
{
// TODO(developer) - handle error appropriately
System
.
err
.
println
(
"Unable to move file: "
+
e
.
getDetails
());
throw
e
;
}
}
}
```


```
import
google.auth
from
googleapiclient.discovery
import
build
from
googleapiclient.errors
import
HttpError
from
googleapiclient.http
import
MediaFileUpload
def
upload_with_conversion
():
"""Upload file with conversion
Returns: ID of the file uploaded
Load pre-authorized user credentials from the environment.
TODO(developer) - See https://developers.google.com/identity
for guides on implementing OAuth2 for the application.
"""
creds
,
_
=
google
.
auth
.
default
()
try
:
# create drive api client
service
=
build
(
"drive"
,
"v3"
,
credentials
=
creds
)
file_metadata
=
{
"name"
:
"My Report"
,
"mimeType"
:
"application/vnd.google-apps.spreadsheet"
,
}
media
=
MediaFileUpload
(
"report.csv"
,
mimetype
=
"text/csv"
,
resumable
=
True
)
# pylint: disable=maybe-no-member
file
=
(
service
.
files
()
.
create
(
body
=
file_metadata
,
media_body
=
media
,
fields
=
"id"
)
.
execute
()
)
print
(
f
'File with ID: "
{
file
.
get
(
"id"
)
}
" has been uploaded.'
)
except
HttpError
as
error
:
print
(
f
"An error occurred:
{
error
}
"
)
file
=
None
return
file
.
get
(
"id"
)
if
__name__
==
"__main__"
:
upload_with_conversion
()
```


```
import
fs
from
'node:fs'
;
import
{
GoogleAuth
}
from
'google-auth-library'
;
import
{
google
}
from
'googleapis'
;
/**
* Uploads a file to Google Drive and converts it to a Google Sheet.
* @return {Promise<string|null|undefined>} The ID of the uploaded file.
*/
async
function
uploadWithConversion
()
{
// Authenticate with Google and get an authorized client.
// TODO (developer): Use an appropriate auth mechanism for your app.
const
auth
=
new
GoogleAuth
({
scopes
:
'https://www.googleapis.com/auth/drive'
,
});
// Create a new Drive API client (v3).
const
service
=
google
.
drive
({
version
:
'v3'
,
auth
});
// The metadata for the file to be uploaded and converted.
const
fileMetadata
=
{
name
:
'My Report'
,
// The MIME type to convert the file to.
mimeType
:
'application/vnd.google-apps.spreadsheet'
,
};
// The media content to be uploaded.
const
media
=
{
mimeType
:
'text/csv'
,
body
:
fs
.
createReadStream
(
'files/report.csv'
),
};
// Upload the file with conversion.
const
file
=
await
service
.
files
.
create
({
requestBody
:
fileMetadata
,
media
,
fields
:
'id'
,
});
// Print the ID of the uploaded file.
console
.
log
(
'File Id:'
,
file
.
data
.
id
);
return
file
.
data
.
id
;
}
```


```
<
?php
use Google\Client;
use Google\Service\Drive;
function uploadWithConversion()
{
try {
$client = new Client();
$client->useApplicationDefaultCredentials();
$client->addScope(Drive::DRIVE);
$driveService = new Drive($client);
$fileMetadata = new Drive\DriveFile(array(
'name' => 'My Report',
'mimeType' => 'application/vnd.google-apps.spreadsheet'));
$content = file_get_contents('../files/report.csv');
$file = $driveService->files->create($fileMetadata, array(
'data' => $content,
'mimeType' => 'text/csv',
'uploadType' => 'multipart',
'fields' => 'id'));
printf("File ID: %s\n", $file->id);
return $file->id;
} catch(Exception $e) {
echo "Error Message: ".$e;
}
}
```


```
using
Google.Apis.Auth.OAuth2
;
using
Google.Apis.Drive.v3
;
using
Google.Apis.Services
;
namespace
DriveV3Snippets
{
// Class to demonstrate Drive's upload with conversion use-case.
public
class
UploadWithConversion
{
/// <summary>
/// Upload file with conversion.
/// </summary>
/// <param name="filePath">Id of the spreadsheet file.</param>
/// <returns>Inserted file id if successful, null otherwise.</returns>
public
static
string
DriveUploadWithConversion
(
string
filePath
)
{
try
{
/* Load pre-authorized user credentials from the environment.
TODO(developer) - See https://developers.google.com/identity for
guides on implementing OAuth2 for your application. */
GoogleCredential
credential
=
GoogleCredential
.
GetApplicationDefault
()
.
CreateScoped
(
DriveService
.
Scope
.
Drive
);
// Create Drive API service.
var
service
=
new
DriveService
(
new
BaseClientService
.
Initializer
{
HttpClientInitializer
=
credential
,
ApplicationName
=
"Drive API Snippets"
});
// Upload file My Report on drive.
var
fileMetadata
=
new
Google
.
Apis
.
Drive
.
v3
.
Data
.
File
()
{
Name
=
"My Report"
,
MimeType
=
"application/vnd.google-apps.spreadsheet"
};
FilesResource
.
CreateMediaUpload
request
;
// Create a new drive.
using
(
var
stream
=
new
FileStream
(
filePath
,
FileMode
.
Open
))
{
// Create a new file, with metadata and stream.
request
=
service
.
Files
.
Create
(
fileMetadata
,
stream
,
"text/csv"
);
request
.
Fields
=
"id"
;
request
.
Upload
();
}
var
file
=
request
.
ResponseBody
;
// Prints the uploaded file id.
Console
.
WriteLine
(
"File ID: "
+
file
.
Id
);
return
file
.
Id
;
}
catch
(
Exception
e
)
{
// TODO(developer) - handle error appropriately
if
(
e
is
AggregateException
)
{
Console
.
WriteLine
(
"Credential Not found"
);
}
else
if
(
e
is
FileNotFoundException
)
{
Console
.
WriteLine
(
"File not found"
);
}
else
{
throw
;
}
}
return
null
;
}
}
}
```

To see if a conversion is available, check the
importFormats
field of the
about
resource before creating the file. Supported
conversions are available dynamically in this array. Some common import formats
are:


| From | To |
| --- | --- |
| Microsoft Word, OpenDocument Text, HTML, RTF, plain text | Google Docs |
| Microsoft Excel, OpenDocument Spreadsheet, CSV, TSV, plain text | Google Sheets |
| Microsoft PowerPoint, OpenDocument Presentation | Google Slides |
| JPEG, PNG, GIF, BMP, PDF | Google Docs (embeds the image in a Doc) |
| Plain text (special MIME type), JSON | Google Apps Script |

When you upload and convert media during an
update
request to a
Docs, Sheets, or Slides file, the
full contents of the document are replaced.

When you convert an image to a Docs, Drive uses
Optical Character Recognition (OCR) to convert the image to text. You can
improve the quality of the OCR algorithm by specifying the applicable
BCP
47
language code in the
ocrLanguage
parameter.
The extracted text appears in the document alongside the embedded image.


## Use a pre-generated ID to upload files

The Drive API lets you retrieve a list of pre-generated file IDs that
can be used to create, copy, and upload resources. For more information, see
Generate IDs to use with your files
.

You can safely retry uploads with pre-generated IDs if there's an indeterminate
server error or timeout. If the file action is successful, subsequent retries
return a
409 Conflict
HTTP status code response and duplicate files aren't
created.

Note that pre-generated IDs aren't supported for the creation of
Google Workspace files, except for the
application/vnd.google-apps.drive-sdk
and
application/vnd.google-apps.folder
MIME
types
. Similarly, uploads referencing a conversion
to a Google Workspace file format aren't supported.


## Define indexable text for unknown file types

Users can use the Drive UI to find document content. You can also
use the
list
method on the
files
resource and the
fullText
field to search for
content from your app. For more information, see
Search for files and
folders
.

Drive automatically indexes documents for search when it
recognizes the file type, including text documents, PDFs, images with text, and
other common types. If your app saves other types of files (such as drawings,
video, and shortcuts), you can improve the discoverability by supplying
indexable text in the
contentHints.indexableText
field of the file.

For more information about indexable text, see
Manage file metadata
.

Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2026-04-20 UTC.


---

# Google Workspace and Google Drive supported MIME types Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/guides/mime-types

- Home
- Google Workspace
- Google Drive
- Reference
You can use MIME types to filter
query
results
or have your app listed in the
Google Workspace Marketplace
index
of apps that can
open specific file types
.

The following table lists
MIME
types
that are
specific to Google Workspace and Drive:


| MIME Type | Description |
| --- | --- |
| application/vnd.google-apps.audio |  |
| application/vnd.google-apps.document | Google Docs |
| application/vnd.google-apps.drive-sdk | Third-party shortcut |
| application/vnd.google-apps.drawing | Google Drawings |
| application/vnd.google-apps.file | Google Drive file |
| application/vnd.google-apps.folder | Google Drive folder |
| application/vnd.google-apps.form | Google Forms |
| application/vnd.google-apps.fusiontable | Google Fusion Tables |
| application/vnd.google-apps.jam | Google Jamboard |
| application/vnd.google-apps.mail-layout | Email layout |
| application/vnd.google-apps.map | Google My Maps |
| application/vnd.google-apps.photo | Google Photos |
| application/vnd.google-apps.presentation | Google Slides |
| application/vnd.google-apps.script | Google Apps Script |
| application/vnd.google-apps.shortcut | Shortcut |
| application/vnd.google-apps.site | Google Sites |
| application/vnd.google-apps.spreadsheet | Google Sheets |
| application/vnd.google-apps.unknown |  |
| application/vnd.google-apps.vid | Google Vids |
| application/vnd.google-apps.video |  |
| application/vnd.google-gemini.gem | Gemini Gem |


## Related topics

- Export MIME types for Google Workspace documents
Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2026-04-20 UTC.


---

# Manage pending access proposals Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/guides/pending-access

- Home
- Google Workspace
- Google Drive
- Guides
An
access proposal
is a proposal from a requester to an approver to grant a
recipient access to a Google Drive item.

An approver can review and act on all unresolved access proposals across
Drive files. This means you can speed up the approval process by
programmatically querying for access proposals and then resolving them. It also
allows proposals to be viewed in aggregate by an approver.

The Google Drive API provides the
accessproposals
resource so you can view
and resolve pending access proposals. The methods of the
accessproposals
resource work on files, folders, the files within a shared drive but
not
on
the shared drive.

The following terms are specific to access proposals:

- Requester
: The user initiating the access proposal to a
Drive item.
- Recipient
: The user receiving the additional permissions on a file if
the access proposal is granted. Many times the recipient is the same as the
requester but not always.
- Approver
: The user responsible for approving (or denying) the access
proposal. This is typically because they're an owner on the document or they
have the ability to share the document.

## Use the fields parameter

If you want to specify the fields to return in the response, you can set the
fields
system
parameter
with any method of the
accessproposals
resource. If you omit the
fields
parameter, the server returns a default set of fields specific to the method. To
return different fields, see
Return specific
fields
.


## Get a pending access proposal

To get an access proposal, use the
get
method on the
accessproposals
resource with the
fileId
and
proposalId
path parameters. If you don't know the proposal ID, you can
list pending access
proposals
using the
list
method.


## List pending access proposals

To list all pending access proposals on a Drive item, call the
list
method on the
accessproposals
resource and include the
fileId
path parameter.

Only approvers on a file can list the pending proposals on a file. An approver
is a user with the
can_approve_access_proposals
capability on the file. If the
requester isn't an approver, an empty list is returned. For more information
about
capabilities
, see
Understand file
capabilities
.

The
response body
consists of an
accessproposals
object representing a list of unresolved access
proposals on the file.

The
accessproposals
object includes info about each proposal such as the
requester, the recipient, and the message that the requester added. It also
includes a
RoleAndView
object that groups the requester's proposed
role
with a
view
. Since
role
is a repeated field, multiples could exist for each proposal. For example, a
proposal might have an
RoleAndView
object of
role=reader
and
view=published
, plus an additional
RoleAndView
object with only the
role=writer
value. For more information, see
Views
.

Pass the following query parameters to customize pagination of, or filter,
access proposals:

- pageToken
: A page token, received from a previous list call. Provide this
token to retrieve the subsequent page.
pageToken
: A page token, received from a previous list call. Provide this
token to retrieve the subsequent page.

- pageSize
: The maximum number of access proposals to return per page.
pageSize
: The maximum number of access proposals to return per page.


## Resolve pending access proposals

To resolve all pending access proposals on a Drive
item, call the
resolve
method on
the
accessproposals
resource and include
the
fileId
and
proposalId
path parameters.

The
resolve
method includes an
action
query parameter that denotes the
action to take on the proposal. The
Action
object tracks the
state change of the proposal so we know if it's being accepted or denied.

The
resolve
method also includes the optional query parameters of
role
and
view
. The only supported roles are
writer
,
commenter
, and
reader
. If the
role isn't specified, it defaults to
reader
. For more information, see
Roles
and permissions
. An additional optional query
parameter of
sendNotification
lets you send an email notification to the
requester when the proposal is accepted or denied.

Just as with the
list
method, users resolving the proposal must have the
can_approve_access_proposals
capability on the file. For more information
about
capabilities
, see
Understand file
capabilities
.

Proposals are resolved using the same patterns listed under
Scenarios for
sharing Drive
resources
. If there are
multiple proposals for the same user, but with different roles, the following
applies:

- If one proposal is accepted and one is denied, the accepted role applies to
the Drive item.
- If both proposals are accepted at the same time, the proposal with the
higher permission (for example,
role=writer
versus
role=reader
) is
applied. The other access proposal is removed from the item.
After sending a proposal to the
resolve
method, the sharing action is
complete. The resolved access proposal is no longer returned through the
list
method. Once the proposal is accepted, the user must use the
permissions
resource to update permissions on a file or
folder. For more information, see
Update
permissions
.


## Related topics

- Share files, folders, and drives
Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2026-04-20 UTC.


---

# Improve performance Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/guides/performance

- Home
- Google Workspace
- Google Drive
- Guides
This document covers some techniques you can use to improve the performance of your application. In some cases, examples from other APIs or generic APIs are used to illustrate the ideas presented. However, the same concepts are applicable to the Google Drive API.


## Compression using gzip

An easy and convenient way to reduce the bandwidth needed for each request is to enable gzip compression. Although this requires additional CPU time to uncompress the results, the trade-off with network costs usually makes it very worthwhile.

In order to receive a gzip-encoded response you must do two things: Set an
Accept-Encoding
header, and modify your user agent to contain the string
gzip
. Here is an example of properly formed HTTP headers for enabling gzip compression:


```
Accept-Encoding:
gzip
User-Agent:
my
program
(
gzip
)
```


## Working with partial resources

Another way to improve the performance of your API calls is by sending and receiving only the portion of the data that you're interested in. This lets your application avoid transferring, parsing, and storing unneeded fields, so it can use resources including network, CPU, and memory more efficiently.

There are two types of partial requests:

- Partial response
: A request where you specify which fields to include in the response (use the
fields
request parameter).
- Patch
: An update request where you send only the fields you want to change (use the
PATCH
HTTP verb).
More details on making partial requests are provided in the following sections.


### Partial response

By default, the server sends back the full representation of a resource after processing requests. For better performance, you can ask the server to send only the fields you really need and get a
partial response
instead.

To request a partial response, use the
fields
request parameter to specify the fields you want returned. You can use this parameter with any request that returns response data.

Note that the
fields
parameter only affects the response data; it does not affect the data that you need to send, if any. To reduce the amount of data you send when modifying resources, use a
patch
request.


### Patch (partial update)

You can also avoid sending unnecessary data when modifying resources. To send updated data only for the specific fields that you’re changing, use the HTTP
PATCH
verb. The patch semantics described in this document are different (and simpler) than they were for the older, GData implementation of partial update.

The short example below shows how using patch minimizes the data you need to send to make a small update.


#### Example


#### Handling the response to a patch

After processing a valid patch request, the API returns a
200 OK
HTTP response code along with the complete representation of the modified resource. If ETags are used by the API, the server updates ETag values when it successfully processes a patch request, just as it does with
PUT
.

The patch request returns the entire resource representation unless you use the
fields
parameter to reduce the amount of data it returns.

If a patch request results in a new resource state that is syntactically or semantically invalid, the server returns a
400 Bad Request
or
422 Unprocessable Entity
HTTP status code, and the resource state remains unchanged. For example, if you attempt to delete the value for a required field, the server returns an error.


#### Alternate notation when PATCH HTTP verb is not supported

If your firewall does not allow HTTP
PATCH
requests, then do an HTTP
POST
request and set the override header to
PATCH
, as shown below:


```bash
POST https://www.googleapis.com/...
X-HTTP-Method-Override: PATCH
...
```


#### Difference between patch and update

In practice, when you send data for an update request that uses the HTTP
PUT
verb, you only need to send those fields which are either required or optional; if you send values for fields that are set by the server, they are ignored. Although this might seem like another way to do a partial update, this approach has some limitations. With updates that use the HTTP
PUT
verb, the request fails if you don't supply required parameters, and it clears previously set data if you don't supply optional parameters.

It's much safer to use patch for this reason. You only supply data for the fields you want to change; fields that you omit are not cleared. The only exception to this rule occurs with repeating elements or arrays: If you omit all of them, they stay just as they are; if you provide any of them, the whole set is replaced with the set that you provide.


## Batch requests

This document shows how to batch API calls together to reduce the number of HTTP connections
your client has to make.
This document is specifically about making a batch request by sending an
HTTP request. If, instead, you're using a Google client library to make a batch request, see the
client library's documentation
.
Overview
Each HTTP connection your client makes results in a certain amount of overhead. The Google Drive API supports batching, to allow your client to put several API calls into a single HTTP request.
Examples of situations when you might want to use batching:
Retrieving metadata for a large number of files.
Updating metadata or properties in bulk.
Changing permissions for a large number of files, such as adding a new user or group.
Synchronizing local client data for the first time or after being offline for an extended time.
In each case, instead of sending each call separately, you can group them together into a single HTTP request. All the inner requests must go to the same Google API.
You're limited to 100 calls in a single batch request. If you must make more calls than that, use multiple batch requests.
Note
: The batch system for the Google Drive API uses the same syntax as the
OData batch processing
system, but the semantics differ.
Additional constraints include:
Batch requests with more than 100 calls might cause an error.
There's an 8,000 character limit on the length of the URL for each inner request.
Google Drive doesn't support batch operations for media, either for upload or download, or for exporting files.
Batch details
A batch request consists of multiple API calls combined into one HTTP request, which can be sent to the
batchPath
specified in the
API discovery document
. The default path is
/batch/
api_name
/
api_version
. This section describes the batch syntax in detail; later, there's an
example
.
Note
: A set of
n
requests batched together counts toward your usage limit as
n
requests, not as one request. The batch request is separated into a set of requests before processing.
Format of a batch request
A batch request is a single standard HTTP request containing multiple Google Drive API calls, using the
multipart/mixed
content type. Within that main HTTP request, each of the parts contains a nested HTTP request.
Each part begins with its own
Content-Type: application/http
HTTP header. It can also have an optional
Content-ID
header. However, the part headers are just there to mark the beginning of the part; they're separate from the nested request. After the server unwraps the batch request into separate requests, the part headers are ignored.
The body of each part is a complete HTTP request, with its own verb, URL, headers, and body. The HTTP request must only contain the path portion of the URL; full URLs are not allowed in batch requests.
The HTTP headers for the outer batch request, except for the
Content-
headers such as
Content-Type
, apply to every request in the batch. If you specify a given HTTP header in both the outer request and an individual call, then the individual call header's value overrides the outer batch request header's value. The headers for an individual call apply only to that call.
For example, if you provide an Authorization header for a specific call, then that header applies only to that call. If you provide an Authorization header for the outer request, then that header applies to all of the individual calls unless they override it with Authorization headers of their own.
When the server receives the batched request, it applies the outer request's query parameters and headers (as appropriate) to each part, and then treats each part as if it were a separate HTTP request.
Response to a batch request
The server's response is a single standard HTTP response with a
multipart/mixed
content type; each part is the response to one of the requests in the batched request, in the same order as the requests.
Like the parts in the request, each response part contains a complete HTTP response, including a status code, headers, and body. And like the parts in the request, each response part is preceded by a
Content-Type
header that marks the beginning of the part.
If a given part of the request had a
Content-ID
header, then the corresponding part of the response has a matching
Content-ID
header, with the original value preceded by the string
response-
, as shown in the following example.
Note
: The server might perform your calls in any order. Don't count on their being executed in the order in which you specified them. If you want to ensure that two calls occur in a given order, you can't send them in a single request; instead, send the first one by itself, then wait for the response to the first one before sending the second one.
Example
The following example shows the use of batching with the Google Drive API.
Example batch request
POST https://www.googleapis.com/batch/drive/v3
Accept-Encoding: gzip
User-Agent: Google-HTTP-Java-Client/1.20.0 (gzip)
Content-Type: multipart/mixed; boundary=
END_OF_PART
Content-Length: 963
--
END_OF_PART
Content-Length: 337
Content-Type: application/http
content-id: 1
content-transfer-encoding: binary
POST https://www.googleapis.com/drive/v3/files/
fileId
/permissions?fields=id
Authorization: Bearer
authorization_token
Content-Length: 70
Content-Type: application/json; charset=UTF-8
{
 "emailAddress":"example@appsrocks.com",
 "role":"writer",
 "type":"user"
}
--
END_OF_PART
Content-Length: 353
Content-Type: application/http
content-id: 2
content-transfer-encoding: binary
POST https://www.googleapis.com/drive/v3/files/
fileId
/permissions?fields=id&sendNotificationEmail=false
Authorization: Bearer
authorization_token
Content-Length: 58
Content-Type: application/json; charset=UTF-8
{
 "domain":"appsrocks.com",
 "role":"reader",
 "type":"domain"
}
--
END_OF_PART
--
Example batch response
This is the response to the example request in the previous section.
HTTP/1.1 200 OK
Alt-Svc: quic=":443"; p="1"; ma=604800
Server: GSE
Alternate-Protocol: 443:quic,p=1
X-Frame-Options: SAMEORIGIN
Content-Encoding: gzip
X-XSS-Protection: 1; mode=block
Content-Type: multipart/mixed; boundary=batch_6VIxXCQbJoQ_AATxy_GgFUk
Transfer-Encoding: chunked
X-Content-Type-Options: nosniff
Date: Fri, 13 Nov 2015 19:28:59 GMT
Cache-Control: private, max-age=0
Vary: X-Origin
Vary: Origin
Expires: Fri, 13 Nov 2015 19:28:59 GMT

This document shows how to batch API calls together to reduce the number of HTTP connections
your client has to make.
This document is specifically about making a batch request by sending an
HTTP request. If, instead, you're using a Google client library to make a batch request, see the
client library's documentation
.
Overview
Each HTTP connection your client makes results in a certain amount of overhead. The Google Drive API supports batching, to allow your client to put several API calls into a single HTTP request.
Examples of situations when you might want to use batching:
Retrieving metadata for a large number of files.
Updating metadata or properties in bulk.
Changing permissions for a large number of files, such as adding a new user or group.
Synchronizing local client data for the first time or after being offline for an extended time.
In each case, instead of sending each call separately, you can group them together into a single HTTP request. All the inner requests must go to the same Google API.
You're limited to 100 calls in a single batch request. If you must make more calls than that, use multiple batch requests.
Note
: The batch system for the Google Drive API uses the same syntax as the
OData batch processing
system, but the semantics differ.
Additional constraints include:
Batch requests with more than 100 calls might cause an error.
There's an 8,000 character limit on the length of the URL for each inner request.
Google Drive doesn't support batch operations for media, either for upload or download, or for exporting files.
Batch details
A batch request consists of multiple API calls combined into one HTTP request, which can be sent to the
batchPath
specified in the
API discovery document
. The default path is
/batch/
api_name
/
api_version
. This section describes the batch syntax in detail; later, there's an
example
.
Note
: A set of
n
requests batched together counts toward your usage limit as
n
requests, not as one request. The batch request is separated into a set of requests before processing.
Format of a batch request
A batch request is a single standard HTTP request containing multiple Google Drive API calls, using the
multipart/mixed
content type. Within that main HTTP request, each of the parts contains a nested HTTP request.
Each part begins with its own
Content-Type: application/http
HTTP header. It can also have an optional
Content-ID
header. However, the part headers are just there to mark the beginning of the part; they're separate from the nested request. After the server unwraps the batch request into separate requests, the part headers are ignored.
The body of each part is a complete HTTP request, with its own verb, URL, headers, and body. The HTTP request must only contain the path portion of the URL; full URLs are not allowed in batch requests.
The HTTP headers for the outer batch request, except for the
Content-
headers such as
Content-Type
, apply to every request in the batch. If you specify a given HTTP header in both the outer request and an individual call, then the individual call header's value overrides the outer batch request header's value. The headers for an individual call apply only to that call.
For example, if you provide an Authorization header for a specific call, then that header applies only to that call. If you provide an Authorization header for the outer request, then that header applies to all of the individual calls unless they override it with Authorization headers of their own.
When the server receives the batched request, it applies the outer request's query parameters and headers (as appropriate) to each part, and then treats each part as if it were a separate HTTP request.
Response to a batch request
The server's response is a single standard HTTP response with a
multipart/mixed
content type; each part is the response to one of the requests in the batched request, in the same order as the requests.
Like the parts in the request, each response part contains a complete HTTP response, including a status code, headers, and body. And like the parts in the request, each response part is preceded by a
Content-Type
header that marks the beginning of the part.
If a given part of the request had a
Content-ID
header, then the corresponding part of the response has a matching
Content-ID
header, with the original value preceded by the string
response-
, as shown in the following example.
Note
: The server might perform your calls in any order. Don't count on their being executed in the order in which you specified them. If you want to ensure that two calls occur in a given order, you can't send them in a single request; instead, send the first one by itself, then wait for the response to the first one before sending the second one.
Example
The following example shows the use of batching with the Google Drive API.
Example batch request
POST https://www.googleapis.com/batch/drive/v3
Accept-Encoding: gzip
User-Agent: Google-HTTP-Java-Client/1.20.0 (gzip)
Content-Type: multipart/mixed; boundary=
END_OF_PART
Content-Length: 963

This document shows how to batch API calls together to reduce the number of HTTP connections
your client has to make.

This document is specifically about making a batch request by sending an
HTTP request. If, instead, you're using a Google client library to make a batch request, see the
client library's documentation
.


## Overview

Each HTTP connection your client makes results in a certain amount of overhead. The Google Drive API supports batching, to allow your client to put several API calls into a single HTTP request.

Examples of situations when you might want to use batching:

- Retrieving metadata for a large number of files.
- Updating metadata or properties in bulk.
- Changing permissions for a large number of files, such as adding a new user or group.
- Synchronizing local client data for the first time or after being offline for an extended time.
In each case, instead of sending each call separately, you can group them together into a single HTTP request. All the inner requests must go to the same Google API.

You're limited to 100 calls in a single batch request. If you must make more calls than that, use multiple batch requests.

Note
: The batch system for the Google Drive API uses the same syntax as the
OData batch processing
system, but the semantics differ.
Additional constraints include:
Batch requests with more than 100 calls might cause an error.
There's an 8,000 character limit on the length of the URL for each inner request.
Google Drive doesn't support batch operations for media, either for upload or download, or for exporting files.

Additional constraints include:

- Batch requests with more than 100 calls might cause an error.
- There's an 8,000 character limit on the length of the URL for each inner request.
- Google Drive doesn't support batch operations for media, either for upload or download, or for exporting files.

## Batch details

A batch request consists of multiple API calls combined into one HTTP request, which can be sent to the
batchPath
specified in the
API discovery document
. The default path is
/batch/
api_name
/
api_version
. This section describes the batch syntax in detail; later, there's an
example
.

Note
: A set of
n
requests batched together counts toward your usage limit as
n
requests, not as one request. The batch request is separated into a set of requests before processing.


### Format of a batch request

A batch request is a single standard HTTP request containing multiple Google Drive API calls, using the
multipart/mixed
content type. Within that main HTTP request, each of the parts contains a nested HTTP request.

Each part begins with its own
Content-Type: application/http
HTTP header. It can also have an optional
Content-ID
header. However, the part headers are just there to mark the beginning of the part; they're separate from the nested request. After the server unwraps the batch request into separate requests, the part headers are ignored.

The body of each part is a complete HTTP request, with its own verb, URL, headers, and body. The HTTP request must only contain the path portion of the URL; full URLs are not allowed in batch requests.

The HTTP headers for the outer batch request, except for the
Content-
headers such as
Content-Type
, apply to every request in the batch. If you specify a given HTTP header in both the outer request and an individual call, then the individual call header's value overrides the outer batch request header's value. The headers for an individual call apply only to that call.

For example, if you provide an Authorization header for a specific call, then that header applies only to that call. If you provide an Authorization header for the outer request, then that header applies to all of the individual calls unless they override it with Authorization headers of their own.

When the server receives the batched request, it applies the outer request's query parameters and headers (as appropriate) to each part, and then treats each part as if it were a separate HTTP request.


### Response to a batch request

The server's response is a single standard HTTP response with a
multipart/mixed
content type; each part is the response to one of the requests in the batched request, in the same order as the requests.

Like the parts in the request, each response part contains a complete HTTP response, including a status code, headers, and body. And like the parts in the request, each response part is preceded by a
Content-Type
header that marks the beginning of the part.

If a given part of the request had a
Content-ID
header, then the corresponding part of the response has a matching
Content-ID
header, with the original value preceded by the string
response-
, as shown in the following example.

Note
: The server might perform your calls in any order. Don't count on their being executed in the order in which you specified them. If you want to ensure that two calls occur in a given order, you can't send them in a single request; instead, send the first one by itself, then wait for the response to the first one before sending the second one.


## Example

The following example shows the use of batching with the Google Drive API.


### Example batch request


```bash
POST https://www.googleapis.com/batch/drive/v3
Accept-Encoding: gzip
User-Agent: Google-HTTP-Java-Client/1.20.0 (gzip)
Content-Type: multipart/mixed; boundary=
END_OF_PART
Content-Length: 963
```

--
END_OF_PART
Content-Length: 337
Content-Type: application/http
content-id: 1
content-transfer-encoding: binary

POST https://www.googleapis.com/drive/v3/files/
fileId
/permissions?fields=id
Authorization: Bearer
authorization_token
Content-Length: 70
Content-Type: application/json; charset=UTF-8

{
 "emailAddress":"example@appsrocks.com",
 "role":"writer",
 "type":"user"
}
--
END_OF_PART
Content-Length: 353
Content-Type: application/http
content-id: 2
content-transfer-encoding: binary

POST https://www.googleapis.com/drive/v3/files/
fileId
/permissions?fields=id&sendNotificationEmail=false
Authorization: Bearer
authorization_token
Content-Length: 58
Content-Type: application/json; charset=UTF-8

{
 "domain":"appsrocks.com",
 "role":"reader",
 "type":"domain"
}
--
END_OF_PART
--


### Example batch response

This is the response to the example request in the previous section.


```
HTTP/1.1 200 OK
Alt-Svc: quic=":443"; p="1"; ma=604800
Server: GSE
Alternate-Protocol: 443:quic,p=1
X-Frame-Options: SAMEORIGIN
Content-Encoding: gzip
X-XSS-Protection: 1; mode=block
Content-Type: multipart/mixed; boundary=batch_6VIxXCQbJoQ_AATxy_GgFUk
Transfer-Encoding: chunked
X-Content-Type-Options: nosniff
Date: Fri, 13 Nov 2015 19:28:59 GMT
Cache-Control: private, max-age=0
Vary: X-Origin
Vary: Origin
Expires: Fri, 13 Nov 2015 19:28:59 GMT
```

--batch_6VIxXCQbJoQ_AATxy_GgFUk
Content-Type: application/http
Content-ID: response-1

HTTP/1.1 200 OK
Content-Type: application/json; charset=UTF-8
Date: Fri, 13 Nov 2015 19:28:59 GMT
Expires: Fri, 13 Nov 2015 19:28:59 GMT
Cache-Control: private, max-age=0
Content-Length: 35

{
 "id": "12218244892818058021i"
}

--batch_6VIxXCQbJoQ_AATxy_GgFUk
Content-Type: application/http
Content-ID: response-2

{
 "id": "04109509152946699072k"
}

--batch_6VIxXCQbJoQ_AATxy_GgFUk--


---

# Display the Google Picker Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/guides/picker

- Home
- Google Workspace
- Google Drive
- Guides
The Google Picker is a "File Open" dialog for information stored on
Google Drive. You can use the
Google Picker API for web
apps
or the
Google Picker API for
desktop apps
to allow users to
open or upload Drive files. The Google Picker API is separate from
the Google Drive API.

Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2026-04-20 UTC.


---

# Add custom file properties Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/guides/properties

- Home
- Google Workspace
- Google Drive
- Guides
Custom file properties
are key-value pairs used to store custom metadata for a
Google Drive file (such as tags), IDs from other data stores, information
shared between workflow applications, and so on. For example, you can add file
properties to all documents generated by the sales department in Q1.

To add properties visible to all applications, use the
properties
field of the
files
resource. To add properties
restricted to your app, use the
appProperties
field of the
files
resource.

Properties can also be used in
search
expressions
.

This is the structure of a typical property that might be used to store a
Drive file's database ID on the file.


### Drive API v3


```
"appProperties": {
  "additionalID": "
ID
",
}
```


### Drive API v2


```
{
  'key':        'additionalID',
  'value':      '
ID
',
  'visibility': 'PRIVATE'
}
```


## Working with custom file properties

The section explains how to perform some custom file property-related tasks that
affect all applications.


### Add or update custom file properties

To add or update properties visible to all applications, use the
files.update
method to set the
properties
field of the
files
resource.


```
PATCH https://www.googleapis.com/drive/v3/files/
FILE_ID
```


```
{
  "properties": {
    "name": "wrench",
    "mass": "1.3kg",
    "count": "3"
  }
}
```

You can also add a custom property to a file using the advanced
Drive service in Google Apps Script. For more information, see
Adding custom
properties
.


### Get or list custom file properties

To view properties visible to all applications, use the
files.get
method to retrieve the
custom file properties for the file.


```bash
GET https://www.googleapis.com/drive/v3/files/
FILE_ID
?fields=properties
```

The response consists of a
properties
object that contains a collection of
key-value pairs.


### Delete custom file properties

To delete property values visible to all applications, use the
files.update
method to set the
properties
field of the
files
resource to null.


```
{
  "name": null
}
```

To view the change, call the
files.get
method to retrieve the
properties
object for the file.


```
{
  "properties": {
    "mass": "1.3kg",
    "count": "3"
  }
}
```


## Limits of custom file properties

Custom properties have the following limits:

- Maximum of 100 custom properties per file, totaled from all sources.
- Maximum of 30 public properties per file, totaled from all sources.
- Maximum of 30 private properties per file from any one application.
- Maximum of 124 bytes per property string (including both key and value) in
UTF-8 encoding. For example, a property with a key that's 10 characters long
can only have 114 characters in the value. Similarly, a property that
requires 100 characters for the value can use up to 24 characters for the
key.
For more information, see the
files
resource. For Drive API v2, see the
properties
resource.


## Access private custom file properties

You can only retrieve private properties using the
appProperties
field through
an authenticated request that uses an access token obtained with an OAuth 2.0
client ID. You cannot use an API key to retrieve private properties.

Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2026-04-23 UTC.


---

# Publish your Drive app Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/guides/publish

- Home
- Google Workspace
- Google Drive
- Guides
Once you've created your Drive app, you can publish it in
Google Workspace Marketplace
for others to use. Domain administrators can install
Google Workspace Marketplace apps on behalf of their users. Additionally,
individual users can find and install Drive apps in
Google Workspace Marketplace or by selecting
New >
add
Connect more apps
in the
Drive UI.

When you publish your app, you are asked to register the file types that the
app can open. When a user views a file in Drive or opens a
Gmail attachment, your application is listed as a suggested app
if the file type is one you have registered.

To make your app available to others, you must follow a publishing process
that creates a listing for your app, registers the file types it can open,
and adds the listing to Google Workspace Marketplace. You should only start
the publishing process once your app is fully functional and you're ready to let
users know about it.


## Before you begin

Before publishing your app to Google Workspace Marketplace, you should decide
on a visibility level and identify collaborators and digital assets.


### Pick a visibility level

Drive app
visibility
refers to the availability of your app to users. There
are two visibility levels:

- Public
visibility indicates that anyone can install the app.
- Private
visibility means only admins or users in your domain can
install the app.

### Identify your collaborators

Collaborators are individuals who have access to update your
app on Google Workspace Marketplace.


### Identify required assets

Before you can publish your Drive app, you must provide specific
digital assets to accompany your app. These assets include information used to
build the store listing and assets that define your app's appearance and
behavior in the Google Drive UI (if applicable). For a list of assets required
to list your app in Google Workspace Marketplace, refer to
Gather your assets
.
For instructions on how to integrate with the Drive UI, including assets
required, refer to
Configure a Drive UI integration
.


## Publish to Google Workspace Marketplace

Once you are ready to publish to Google Workspace Marketplace,
refer to
How to publish
.

Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2026-04-23 UTC.


---

# Notifications for resource changes Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/guides/push

- Home
- Google Workspace
- Google Drive
- Guides
This document describes how to use push notifications that inform your
application when a resource changes.


## Overview

The Google Drive API provides push notifications that let you monitor
 changes in resources. You can use this feature to improve the performance of
 your application. It lets you eliminate the extra network and compute
 costs involved with polling resources to determine if they have changed.
 Whenever a watched resource changes, the Google Drive API notifies your
 application.

To use push notifications, you must do two things:

- Set up your receiving URL or "webhook" callback receiver.
This
 is an HTTPS server that handles the API notification messages that are
 triggered when a resource changes.
Set up your receiving URL or "webhook" callback receiver.

This
 is an HTTPS server that handles the API notification messages that are
 triggered when a resource changes.

- Set up a (
notification channel
) for each resource endpoint you want to
 watch.
A channel specifies routing information for notification
 messages. As part of the channel setup, you must identify the specific URL where
 you want to receive notifications. Whenever a channel's resource changes,
 the Google Drive API sends a notification message as a
POST
request to that URL.
Set up a (
notification channel
) for each resource endpoint you want to
 watch.

A channel specifies routing information for notification
 messages. As part of the channel setup, you must identify the specific URL where
 you want to receive notifications. Whenever a channel's resource changes,
 the Google Drive API sends a notification message as a
POST
request to that URL.

Currently, the Google Drive API supports notifications for changes to
 the
files
and
changes
methods.


## Create notification channels

To request push notifications, you must set up a notification channel
 for each resource you want to monitor. After your notification channels are set
 up, the Google Drive API informs your application when any watched resource
 changes.


### Make watch requests

Each watchable Google Drive API resource has an associated
watch
method at a URI of the following form:


```
https://www.googleapis.com/
API_NAME
/
API_VERSION
/
RESOURCE_PATH
/watch
```

To set up a notification channel for messages about changes to a
 particular resource, send a
POST
request to the
watch
method for the resource.

Each notification channel is associated both with a particular user and
 a particular resource (or set of resources). A
watch
request
 won't be successful unless the current user
 
 
 or service account
 
 
 owns or has permission to access this resource.


#### Examples

The following code sample shows how to use a
channels
resource to start watching for changes to a single
files
resource using the
files.watch
method:


```bash
POST https://www.googleapis.com/drive/v3/files/
fileId
/watch
Authorization: Bearer
CURRENT_USER_AUTH_TOKEN
Content-Type: application/json

{
  "id": "01234567-89ab-cdef-0123456789ab",
  "type": "web_hook",
  "address": "https://mydomain.com/notifications",
  ...
  "token": "target=myApp-myFilesChannelDest",
  "expiration": 1426325213000
}
```

In the request body, provide your channel
id
,
the
type
as
web_hook
, and your receiving URL in
address
.
You can also optionally provide:

- A
token
to use as your channel token.
- An
expiration
time in milliseconds for your requested channel expiration time.
The following code sample shows how to use a
channels
resource to start watching for all
changes
using the
changes.watch
method:


```bash
POST https://www.googleapis.com/drive/v3/changes/watch
Authorization: Bearer
CURRENT_USER_AUTH_TOKEN
Content-Type: application/json

{
  "id": "4ba78bf0-6a47-11e2-bcfd-0800200c9a77",
  "type": "web_hook",
  "address": "https://mydomain.com/notifications",
  ...
  "token": "target=myApp-myChangesChannelDest",
  "expiration": 1426325213000
}
```


#### Required properties

With each
watch
request, you must provide these fields:

- An
id
property string that uniquely identifies this
 new notification channel within your project. We recommend using
 a universally unique identifier
 (
UUID
) or any similar
 unique string. Maximum length: 64 characters.
The ID value you set is echoed back in the
X-Goog-Channel-Id
HTTP header of every notification
 message that you receive for this channel.
A
type
property string set to the value
web_hook
.
An
address
property string set to the URL that listens
 and responds to notifications for this notification channel. This is
 your webhook callback URL, and it must use HTTPS.
Note that the Google Drive API is able to send notifications to
 this HTTPS address only if there's a valid SSL certificate installed
 on your web server. Invalid certificates include:
Self-signed certificates.
Certificates signed by an untrusted source.
Certificates that have been revoked.
Certificates that have a subject that doesn't match the target
 hostname.
An
id
property string that uniquely identifies this
 new notification channel within your project. We recommend using
 a universally unique identifier
 (
UUID
) or any similar
 unique string. Maximum length: 64 characters.

The ID value you set is echoed back in the
X-Goog-Channel-Id
HTTP header of every notification
 message that you receive for this channel.

- A
type
property string set to the value
web_hook
.
A
type
property string set to the value
web_hook
.

- An
address
property string set to the URL that listens
 and responds to notifications for this notification channel. This is
 your webhook callback URL, and it must use HTTPS.
Note that the Google Drive API is able to send notifications to
 this HTTPS address only if there's a valid SSL certificate installed
 on your web server. Invalid certificates include:
Self-signed certificates.
Certificates signed by an untrusted source.
Certificates that have been revoked.
Certificates that have a subject that doesn't match the target
 hostname.
An
address
property string set to the URL that listens
 and responds to notifications for this notification channel. This is
 your webhook callback URL, and it must use HTTPS.

Note that the Google Drive API is able to send notifications to
 this HTTPS address only if there's a valid SSL certificate installed
 on your web server. Invalid certificates include:

- Self-signed certificates.
- Certificates signed by an untrusted source.
- Certificates that have been revoked.
- Certificates that have a subject that doesn't match the target
 hostname.

#### Optional properties

You can also specify these optional fields with your
watch
request:

- A
token
property that specifies an arbitrary string
 value to use as a channel token. You can use notification channel
 tokens for various purposes. For example, you can use the
 token to verify that each incoming message is for a channel that your
 application created—to ensure that the notification is not being
 spoofed—or to route the message to the right destination within
 your application based on the purpose of this channel. Maximum length:
 256 characters.
The token is included in the
X-Goog-Channel-Token
HTTP header in every notification
 message that your application receives for this channel.
If you use notification channel tokens, we recommend that you:
Use an extensible encoding format, such as URL query
 parameters. Example:
forwardTo=hr&createdBy=mobile
Don't include sensitive data such as OAuth tokens.
A
token
property that specifies an arbitrary string
 value to use as a channel token. You can use notification channel
 tokens for various purposes. For example, you can use the
 token to verify that each incoming message is for a channel that your
 application created—to ensure that the notification is not being
 spoofed—or to route the message to the right destination within
 your application based on the purpose of this channel. Maximum length:
 256 characters.

The token is included in the
X-Goog-Channel-Token
HTTP header in every notification
 message that your application receives for this channel.

If you use notification channel tokens, we recommend that you:

- Use an extensible encoding format, such as URL query
 parameters. Example:
forwardTo=hr&createdBy=mobile
Use an extensible encoding format, such as URL query
 parameters. Example:
forwardTo=hr&createdBy=mobile

- Don't include sensitive data such as OAuth tokens.
Don't include sensitive data such as OAuth tokens.

- An
expiration
property string set to a
Unix timestamp
(in milliseconds) of the date and time when you want the Google Drive API to
 stop sending messages for this notification channel.
If a channel has an expiration time, it's included as the value
 of the
X-Goog-Channel-Expiration
HTTP header (in human-readable
 format) in every notification message that your
 application receives for this channel.
An
expiration
property string set to a
Unix timestamp
(in milliseconds) of the date and time when you want the Google Drive API to
 stop sending messages for this notification channel.

If a channel has an expiration time, it's included as the value
 of the
X-Goog-Channel-Expiration
HTTP header (in human-readable
 format) in every notification message that your
 application receives for this channel.

For more details on the request, refer to the
watch
method
 for the
files
and
changes
methods in the API Reference.


#### Watch response

If the
watch
request successfully creates a notification
 channel, it returns an HTTP
200 OK
status code.

The message body of the watch response provides information about the
 notification channel you just created, as shown in the example below.


```
{
  "kind": "api#channel",
  "id": "01234567-89ab-cdef-0123456789ab",
  "resourceId": "o3hgv1538sdjfh",
  "resourceUri": "https://www.googleapis.com/drive/v3/files/o3hgv1538sdjfh",
  "token": "target=myApp-myFilesChannelDest",
  "expiration": 1426325213000
}
```

The response body provides channel details such as:

- kind
: Identifies this as an API channel resource.
- id
: The ID you specified for this channel.
- resourceId
: The ID of the watched resource.
- resourceUri
: The version-specific ID of the watched resource.
- token
: The token provided in the request body.
- expiration
: The channel expiration time as a Unix timestamp in milliseconds.
In addition to the properties you sent as part of your request, the
 returned information also includes the
resourceId
and
resourceUri
to identify the resource being watched on this
 notification channel.

You can pass the returned information to other notification channel
 operations, such as when you want to
stop receiving
 notifications
.

For more details on the response, refer to the
watch
method for the
files
and
changes
methods in the API Reference.


#### Sync message

After creating a notification channel to watch a resource, the
 Google Drive API sends a
sync
message to indicate that
 notifications are starting. The
X-Goog-Resource-State
HTTP
 header value for these messages is
sync
. Due to network
 timing issues, it's possible to receive the
sync
message
 even before you receive the
watch
method response.

It's safe to ignore the
sync
notification, but you can
 also use it. For example, if you decide you don't want to keep
 the channel, you can use the
X-Goog-Channel-ID
and
X-Goog-Resource-ID
values in a call to
stop receiving notifications
. You can also use the
sync
notification to do some initialization to prepare for
 later events.

The format of
sync
messages the Google Drive API sends to
 your receiving URL is shown below.


```bash
POST https://mydomain.com/notifications // Your receiving URL.
X-Goog-Channel-ID: channel-ID-value
X-Goog-Channel-Token: channel-token-value
X-Goog-Channel-Expiration: expiration-date-and-time // In human-readable format. Present only if the channel expires.
X-Goog-Resource-ID: identifier-for-the-watched-resource
X-Goog-Resource-URI: version-specific-URI-of-the-watched-resource
X-Goog-Resource-State: sync
X-Goog-Message-Number: 1
```

Sync messages always have an
X-Goog-Message-Number
HTTP
 header value of
1
. Each subsequent notification for this channel has
 a message number that's larger than the previous one, though the message
 numbers will not be sequential.


### Renew notification channels

A notification channel can have an expiration time, with a value
 determined either by your request or by any Google Drive API internal limits
 or defaults (the more restrictive value is used). The channel's expiration
 time, if it has one, is included as a
Unix timestamp
(in milliseconds) in the information returned by the
watch
method. In addition, the
 expiration date and time is included (in human-readable format) in every
 notification message your application receives for this channel in the
X-Goog-Channel-Expiration
HTTP header.

Currently, there's no automatic way to renew a notification channel. When
 a channel is close to its expiration, you must replace it with a new one by calling
 the
watch
method. As always, you must use a unique value for
 the
id
property of the new channel. Note that there's likely
 to be an "overlap" period of time when the two notification channels for the
 same resource are active.


## Receive notifications

Whenever a watched resource changes, your application receives a
 notification message describing the change. The Google Drive API sends these
 messages as HTTPS
POST
requests to the URL you specified as the
address
property
for this notification
 channel.


### Interpret the notification message format

All notification messages include a set of HTTP headers that have
X-Goog-
prefixes.
 Some types of notifications can also include a
 message body.


#### Headers

Notification messages posted by the Google Drive API to your receiving
 URL include the following HTTP headers:


| Header | Description |
| --- | --- |
| Always present |  |
| X-Goog-Channel-ID | UUID or other unique string you provided to identify this
 notification channel. |
| X-Goog-Message-Number | Integer that identifies this message for this notification
 channel. Value is always
1
for
sync
messages. Message
 numbers increase for each subsequent message on the channel, but they're
 not sequential. |
| X-Goog-Resource-ID | An opaque value identifying the watched resource. This ID is
 stable across API versions. |
| X-Goog-Resource-State | The new resource state that triggered the notification.
 Possible values:
sync
,
add
,
remove
,
update
,
trash
,
untrash
, or
change
. |
| X-Goog-Resource-URI | An API-version-specific identifier for the watched resource. |
| Sometimes present |  |
| X-Goog-Changed | Additional details about the changes.
 Possible values:
content
,
parents
,
children
, or
permissions
.
 Not provided with
sync
messages. |
| X-Goog-Channel-Expiration | Date and time of notification channel expiration, expressed in
 human-readable format. Only present if defined. |
| X-Goog-Channel-Token | Notification channel token that was set by your application, and
 that you can use to verify the notification source. Only present if
 defined. |

Notification messages for
files
and
changes
are empty.

Change notification message for
files
resources, which doesn't include a request body:


```bash
POST https://mydomain.com/notifications
Content-Type: application/json; utf-8
Content-Length: 0
X-Goog-Channel-ID: 4ba78bf0-6a47-11e2-bcfd-0800200c9a66
X-Goog-Channel-Token: 398348u3tu83ut8uu38
X-Goog-Channel-Expiration: Tue, 19 Nov 2013 01:13:52 GMT
X-Goog-Resource-ID:  ret08u3rv24htgh289g
X-Goog-Resource-URI: https://www.googleapis.com/drive/v3/files/ret08u3rv24htgh289g
X-Goog-Resource-State:  update
X-Goog-Changed: content,properties
X-Goog-Message-Number: 10
```

Change notification message for
changes
resources, which includes a request body:


```bash
POST https://mydomain.com/notifications
Content-Type: application/json; utf-8
Content-Length: 118
X-Goog-Channel-ID: 8bd90be9-3a58-3122-ab43-9823188a5b43
X-Goog-Channel-Token: 245t1234tt83trrt333
X-Goog-Channel-Expiration: Tue, 19 Nov 2013 01:13:52 GMT
X-Goog-Resource-ID:  ret987df98743md8g
X-Goog-Resource-URI: https://www.googleapis.com/drive/v3/changes
X-Goog-Resource-State:  changed
X-Goog-Message-Number: 23

{
  "kind": "drive#changes"
}
```


### Respond to notifications

To indicate success, you can return any of the following status codes:
200
,
201
,
202
,
204
, or
102
.

If your service uses
Google's API client library
and returns
500
,
502
,
503
, or
504
, the Google Drive API
 retries with
exponential backoff
.
 Every other return status code is considered to be a message failure.


### Understand Google Drive API notification events

This section provides details on the notification messages you can
 receive when using push notifications with the Google Drive API.


| X-Goog-Resource-State | Applies to | Delivered when |
| --- | --- | --- |
| sync | files
,
changes | A channel was successfully created. You can expect to start receiving notifications for it. |
| add | files | A resource was created or shared. |
| remove | files | An existing resource was deleted or unshared. |
| update | files | One or more properties (metadata) of a resource have been updated. |
| trash | files | A resource has been moved to the trash. |
| untrash | files | A resource has been removed from the trash. |
| change | changes | One or more changelog items have been added. |

For
update
events, the
X-Goog-Changed
HTTP header might be provided. That header contains a comma-separated list that describes the types of changes that have occurred.


| Change type | Indicates |
| --- | --- |
| content | The resource content has been updated. |
| properties | One or more resource properties have been updated. |
| parents | One or more resource parents have been added or removed. |
| children | One or more resource children have been added or removed. |
| permissions | The resource permissions have been updated. |

Example with
X-Goog-Changed
header:


```
X-Goog-Resource-State: update
X-Goog-Changed: content, permissions
```


## Stop notifications

The
expiration
property controls when the notifications stop automatically. You can
 choose to stop receiving notifications for a particular channel before it
 expires by calling the
stop
method at
 
 the following URI:


```
https://www.googleapis.com/drive/v3/channels/stop
```

This method requires that you provide at least the channel's
id
and the
resourceId
properties, as shown in the
 example below. Note that if the Google Drive API has several types of
 resources that have
watch
methods, there's only one
stop
method.

Only users with the right permission can stop a channel. In particular:

- If the channel was created by a regular user account, only the same
 user from the same client (as identified by the OAuth 2.0 client IDs from the
 auth tokens) who created the channel can stop the channel.
- If the channel was created by a service account, any user from the same
 client can stop the channel.
The following code sample shows how to stop receiving notifications:


```bash
POST https://www.googleapis.com/drive/v3/channels/stop
  
Authorization: Bearer
CURRENT_USER_AUTH_TOKEN
Content-Type: application/json

{
  "id": "4ba78bf0-6a47-11e2-bcfd-0800200c9a66",
  "resourceId": "ret08u3rv24htgh289g"
}
```

Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2026-04-23 UTC.


---

# Export MIME types for Google Workspace documents Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/guides/ref-export-formats

- Home
- Google Workspace
- Google Drive
- Reference
The following table shows how Google Workspace documents map to export
MIME
types
:


| Document Type | Format | MIME Type | File Extension |
| --- | --- | --- | --- |
| Documents | Microsoft Word | application/vnd.openxmlformats-officedocument.wordprocessingml.document | .docx |
|  | OpenDocument | application/vnd.oasis.opendocument.text | .odt |
|  | Rich Text | application/rtf | .rtf |
|  | PDF | application/pdf | .pdf |
|  | Plain Text | text/plain | .txt |
|  | Web Page (HTML) | application/zip | .zip |
|  | EPUB | application/epub+zip | .epub |
|  | Markdown | text/markdown | .md |
| Spreadsheets | Microsoft Excel | application/vnd.openxmlformats-officedocument.spreadsheetml.sheet | .xlsx |
|  | OpenDocument | application/vnd.oasis.opendocument.spreadsheet | .ods |
|  | PDF | application/pdf | .pdf |
|  | Web Page (HTML) | application/zip | .zip |
|  | Comma Separated Values (first-sheet only) | text/csv | .csv |
|  | Tab Separated Values (first-sheet only) | text/tab-separated-values | .tsv |
| Presentations | Microsoft PowerPoint | application/vnd.openxmlformats-officedocument.presentationml.presentation | .pptx |
|  | ODP | application/vnd.oasis.opendocument.presentation | .odp |
|  | PDF | application/pdf | .pdf |
|  | Plain Text | text/plain | .txt |
|  | JPEG (first-slide only) | image/jpeg | .jpg |
|  | PNG (first-slide only) | image/png | .png |
|  | Scalable Vector Graphics (first-slide only) | image/svg+xml | .svg |
| Drawings | PDF | application/pdf | .pdf |
|  | JPEG | image/jpeg | .jpg |
|  | PNG | image/png | .png |
|  | Scalable Vector Graphics | image/svg+xml | .svg |
| Apps Script | JSON | application/vnd.google-apps.script+json | .json |
| Google Vids | MP4 | video/mp4 | .mp4 |

To view a list of all system supported export formats for a user, use the
get
method on the
about
resource with the
fields
parameter set to
exportFormats
.

You can also export Google Workspace
documents using Google Apps Script. For more information on supported formats
when exporting content in Apps Script, see the reference
documentation for
Google Docs
,
Google Sheets
,
and
Google Slides
.


## Related topics

- Google Workspace and Google Drive supported MIME types
- Return user info
Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2026-04-20 UTC.


---

# Roles and permissions Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/guides/ref-roles

- Home
- Google Workspace
- Google Drive
- Reference
A
role
is a
collection of
permissions
that allows users to
perform specific actions on Google Drive resources. To make permissions
available to users, groups, and service accounts, you assign roles. When you
assign a role, you grant all the permissions that the role contains.

Each permission in the Google Drive API has a role that defines what users can do
with a file, folder, or shared drive. For more information, see
Scenarios for
sharing Drive
resources
.


## Operations for files and folders

The following table shows the operations users can perform for each role, when
the role isn't restricted to a view. For more information, see
Views
.


| Permitted operation | owner | organizer | fileOrganizer | writer | commenter | reader |
| --- | --- | --- | --- | --- | --- | --- |
| Read the metadata (such as name, description) of the file or folder |  |  |  |  |  |  |
| Read the content of the file |  |  |  |  |  |  |
| Read the list of items in the folder |  |  |  |  |  |  |
| Add comments to the file |  |  |  |  |  |  |
| Modify the metadata of the file or folder |  |  |  |  |  |  |
| Modify the content of the file |  |  |  |  |  |  |
| Access historical revisions |  |  |  |  |  |  |
| Add items to the folder |  |  |  |  |  |  |
| Remove items from the My Drive folder |  |  |  |  |  |  |
| Share items from the My Drive folder |  |  |  |  |  |  |
| Can access detailed file permissions |  |  |  |  |  |  |
| Move items into the trash |  |  |  |  |  |  |
| Recover items from the trash |  |  |  |  |  |  |
| Empty the trash |  |  |  |  |  |  |
| Delete a file or folder |  |  |  |  |  |  |
| Add a content restriction to a file in a My Drive folder |  |  |  |  |  |  |
| Set or unset the limited access setting in My Drive folders |  |  |  |  |  |  |


## Operations specific to shared drives

The following table shows shared drive specific operations users can perform for
each role, when the role isn't restricted to a view. For more information, see
Views
.


| Permitted operation | owner | organizer | fileOrganizer | writer | commenter | reader |
| --- | --- | --- | --- | --- | --- | --- |
| Share a shared drive item |  |  |  |  |  |  |
| Add files to shared drives |  |  |  |  |  |  |
| Modify the metadata of a shared drive |  |  |  |  |  |  |
| Add shared drive members |  |  |  |  |  |  |
| Reorganize items within a shared drive [1] |  |  |  |  |  |  |
| Move items outside of a shared drive [2] |  |  |  |  |  |  |
| Delete items in shared drives [2] |  |  |  |  |  |  |
| Delete an empty shared drive |  |  |  |  |  |  |
| Add a content restriction to a file in a shared drive |  |  |  |  |  |  |
| Set or unset the limited access setting in shared drive folders |  |  |  |  |  |  |


## Correlation between Drive API and Drive UI roles

The Drive API and Drive UI use the same underlying
permission system. However, the role names differ slightly between the two.

The following table shows how the roles correspond for files and folders in My
Drive.


| Drive API role | Drive UI role | Description |
| --- | --- | --- |
| owner | Owner | Grants full control over the file or folder. |
| writer | Editor | Grants the ability to view the file, add comments, and edit the file. For folders, can add, edit, and delete files or subfolders within that folder. |
| commenter | Commenter | Grants the ability to view the file and add comments. |
| reader | Viewer | Grants the ability to view the file. |

The following table shows how the roles correspond for files and folders in
shared drives.


| Drive API role | Drive UI role | Description |
| --- | --- | --- |
| organizer | Manager | Grants the ability to manage files, folders, people, and settings. |
| fileOrganizer | Content Manager | Grants the ability to contribute and manage content. Default role for new members. |
| writer | Contributor | Grants the ability to view the file, add comments, and edit the file. Can also create files within a shared drive. |
| commenter | Commenter | Grants the ability to view the file and add comments. |
| reader | Viewer | Grants the ability to view the file. |


## Views

A permission might be restricted to a
view
, in which case
the role only applies to that particular view.

A permission with
view=published
and
role=reader
grants
reader
access to
the published view of the file, but it doesn't grant
reader
access to the
file.

A permission with
view=metadata
and
role=reader
grants
reader
access to
the metadata of the folder, but it doesn't grant access to the folder's
contents.

Conversely, any permission that's not restricted to a particular view, grants
reader
access to the published view of the file.


## Related topics

- Share files from Google Drive
- How file access works in shared drives
Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2026-04-20 UTC.


---

# Search query terms and operators Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/guides/ref-search-terms

- Home
- Google Workspace
- Google Drive
- Reference
This reference guide provides query terms and operators you can use with the
Google Drive API to filter for files, folders, and shared drives.

For file search examples, see
Search for files and
folders
.

For example searches of shared drives, see
Search for shared drives
.


## Query string syntax

A query string contains the following three parts:

query_term operator values

Where:

- query_term
is the query term or field to search upon.
query_term
is the query term or field to search upon.

- operator
specifies the condition for the query term.
operator
specifies the condition for the query term.

- values
are the specific values you want to use to filter your search
results.
values
are the specific values you want to use to filter your search
results.


## Query operators

The following table lists the valid query operators:


| Operator | Usage |
| --- | --- |
| contains | The content of one string is present in the other. |
| = | The content of a string or boolean is equal to the other. |
| != | The content of a string or boolean is not equal to the other. |
| < | A value is less than another. |
| <= | A value is less than or equal to another. |
| > | A value is greater than another. |
| >= | A value is greater than or equal to another. |
| in | An element is contained within a collection. |
| and | Return items that match both queries. |
| or | Return items that match either query. |
| not | Negates a search query. |
| has | A collection contains an element matching the parameters. |


## File-specific query terms

The following table lists all valid file query terms. For data types and
descriptions, refer to the
files
resource
reference.


| Query term | Valid operators | Usage |
| --- | --- | --- |
| name | contains
,
=
,
!= | Name of the file. Surround with single quotes (
'
). Escape single quotes in queries with
\'
, such as
'Valentine\'s Day'
. |
| fullText | contains | Whether the
name
,
description
,
indexableText
properties, or text in the file's content or metadata of the file matches. Surround with single quotes (
'
). Escape single quotes in queries with
\'
, such as
'Valentine\'s Day'
. |
| mimeType | contains
,
=
,
!= | MIME type of the file. Surround with single quotes (
'
). Escape single quotes in queries with
\'
, such as
'Valentine\'s Day'
. For further information on MIME types, see
Google Workspace and Google Drive supported MIME types
. |
| modifiedTime | <=
,
<
,
=
,
!=
,
>
,
>= | Date of the last file modification.
RFC 3339
format, default time zone is UTC, such as
2012-06-04T12:00:00-08:00
. Fields of type
date
are not comparable to each other, only to constant dates. |
| viewedByMeTime | <=
,
<
,
=
,
!=
,
>
,
>= | Date that the user last viewed a file.
RFC 3339
format, default time zone is UTC, such as
2012-06-04T12:00:00-08:00
. Fields of type
date
are not comparable to each other, only to constant dates. |
| trashed | =
,
!= | Whether the file is in the trash or not. Can be either
true
or
false
. |
| starred | =
,
!= | Whether the file is starred or not. Can be either
true
or
false
. |
| parents | in | Whether the parents collection contains the specified ID. |
| owners | in | Users who own the file. |
| writers | in | Users or groups who have permission to modify the file. See the
permissions
resource reference. |
| readers | in | Users or groups who have permission to read the file. See the
permissions
resource reference. |
| sharedWithMe | =
,
!= | Files that are in the user's
"Shared with me" collection
. All file users are in the file's Access Control List (ACL). Can be either
true
or
false
. |
| createdTime | <=
,
<
,
=
,
!=
,
>
,
>= | Date when the file was created. Use
RFC 3339
format, default time zone is UTC, such as
2012-06-04T12:00:00-08:00
. Supported in Drive API v3 only. |
| properties | has | Public custom file properties. |
| appProperties | has | Private custom file properties. |
| visibility | =
,
!= | The visibility level of the file. Valid values are
anyoneCanFind
,
anyoneWithLink
,
domainCanFind
,
domainWithLink
, and
limited
. Surround with single quotes (
'
). |
| shortcutDetails.targetId | =
,
!= | The ID of the item the shortcut points to. |

The following demonstrates operator and query term combinations:

- The
contains
operator only performs prefix matching for a
name
term. For example, suppose you have a name
of
HelloWorld
. A query of
name contains 'Hello'
returns a
result, but a query of
name contains 'World'
doesn't.
The
contains
operator only performs prefix matching for a
name
term. For example, suppose you have a name
of
HelloWorld
. A query of
name contains 'Hello'
returns a
result, but a query of
name contains 'World'
doesn't.

- The
contains
operator only performs matching on entire string tokens for
the
fullText
term. For example, if the full text of a document contains
the string "HelloWorld", only the query
fullText contains 'HelloWorld'
returns a result.
The
contains
operator only performs matching on entire string tokens for
the
fullText
term. For example, if the full text of a document contains
the string "HelloWorld", only the query
fullText contains 'HelloWorld'
returns a result.

- The
contains
operator matches a phrase if the right operand is surrounded
by double quotes. For example:
If the
fullText
of a document contains the string "Hello there world",
then the query
fullText contains '"Hello there"'
returns a result, but the
query
fullText contains '"Hello world"'
doesn't.
If the full text of a document contains the string "Hello_world", then
the query
fullText contains '"Hello world"'
still returns a result as
the underscore in the document string is treated as a space.
The
contains
operator matches a phrase if the right operand is surrounded
by double quotes. For example:

- If the
fullText
of a document contains the string "Hello there world",
then the query
fullText contains '"Hello there"'
returns a result, but the
query
fullText contains '"Hello world"'
doesn't.
If the
fullText
of a document contains the string "Hello there world",
then the query
fullText contains '"Hello there"'
returns a result, but the
query
fullText contains '"Hello world"'
doesn't.

- If the full text of a document contains the string "Hello_world", then
the query
fullText contains '"Hello world"'
still returns a result as
the underscore in the document string is treated as a space.
If the full text of a document contains the string "Hello_world", then
the query
fullText contains '"Hello world"'
still returns a result as
the underscore in the document string is treated as a space.

- The
owners
,
writers
, and
readers
terms are indirectly reflected in the
permissions
list and refer to the
role
on the permission. For a complete list of role permissions, see
Roles and
permissions
.
The
owners
,
writers
, and
readers
terms are indirectly reflected in the
permissions
list and refer to the
role
on the permission. For a complete list of role permissions, see
Roles and
permissions
.

For more examples of query string searches, see
file query string examples
.


## Shared drive-specific query terms

The following table lists all valid shared drive query terms. For data types and
descriptions, see the
drives
resource reference.


| Query term | Valid operators | Usage | useDomainAdminAccess
setting |
| --- | --- | --- | --- |
| createdTime | <=
,
<
,
=
,
!=
,
>
,
>= | Date when the shared drive was created.
RFC 3339
format, default time zone is UTC, such as
2012-06-04T12:00:00-08:00
. | true |
| hidden | =
,
!= | Specifies whether the shared drive is hidden. Can be either
true
or
false
. | false |
| memberCount | <=
,
<
,
=
,
!=
,
>
,
>= | Number of users and groups that are members of the shared drive. Takes a numerical value. | true |
| name | contains
,
=
,
!= | Name of the shared drive. Surround with single quotes (
'
). Escape single quotes in queries with
\'
, such as
'Valentine\'s Day'
. | true |
| organizerCount | <=
,
<
,
=
,
!=
,
>
,
>= | Number of users and groups that are organizers of the shared drive. Takes a numerical value. | true |
| orgUnitId | =
,
!= | The organizational unit ID of a shared drive. Takes a string value. | true |

For more examples of query string searches, see
shared drive query string
examples
.


## Related topics

- Search for files and folders
- Search for shared drives
- Google Workspace and Google Drive supported MIME types
- Roles and permissions
Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2026-04-20 UTC.


---

# Remove a label from a file Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/guides/remove-label

- Home
- Google Workspace
- Google Drive
- Guides
This page describes how to remove a label on a single Google Drive file.

To remove the file label metadata from a file, use the
files.modifyLabels
method. The
request body
contains an instance of
ModifyLabelsRequest
to modify the set of labels on a file. The request might contain several
modifications that are applied atomically. That is, if any modifications aren't
valid, then the entire update is unsuccessful and none of the (potentially
dependent) changes are applied.

The
ModifyLabelsRequest
contains an instance of
LabelModification
which is a modification to a label on a file. It might also contain an instance
of
FieldModification
which is a modification to a label's field. To remove the label from the file,
set
FieldModification.removeLabel
to
True
.

If successful, the
response
body
contains
the labels added or updated by the request. These exist within a
modifiedLabels
object of type
Label
.


## Example

The following code sample shows how to use the
labelId
to remove all fields
associated with the label using the
fileId
. For example, if a label contains
both text and user fields, removing a label deletes
both
the text and user 
fields associated with the label. Whereas, unsetting the text field removes it 
from the label but leaves the user field untouched. For more information, see
Unset a label field on a file
.


### Java


```
ModifyLabelsRequest
modifyLabelsRequest
=
new
ModifyLabelsRequest
()
.
setLabelModifications
(
ImmutableList
.
of
(
new
LabelModification
()
.
setLabelId
(
"
LABEL_ID
"
)
.
setRemoveLabel
(
true
)));
ModifyLabelsResponse
modifyLabelsResponse
=
driveService
.
files
().
modifyLabels
(
"
FILE_ID
"
,
modifyLabelsRequest
).
execute
();
```


### Python


```
label_modification
=
{
'labelId'
:
'
LABEL_ID
'
,
'removeLabel'
:
True
]}
modified_labels
=
drive_service
.
files
()
.
modifyLabels
(
fileId
=
"
FILE_ID
"
,
body
=
{
'labelModifications'
:
[
label_modification
]})
.
execute
();
```


### Node.js


```
/**
* Remove a label on a Drive file
* @return{obj} updated label data
**/
async
function
removeLabel
()
{
// Get credentials and build service
// TODO (developer) - Use appropriate auth mechanism for your app
const
{
GoogleAuth
}
=
require
(
'google-auth-library'
);
const
{
google
}
=
require
(
'googleapis'
);
const
auth
=
new
GoogleAuth
({
scopes
:
'https://www.googleapis.com/auth/drive'
});
const
service
=
google
.
drive
({
version
:
'v3'
,
auth
});
const
labelModification
=
{
'labelId'
:
'
LABEL_ID
'
,
'removeLabel'
:
True
,
};
const
labelModificationRequest
=
{
'labelModifications'
:
[
labelModification
],
};
try
{
const
updateResponse
=
await
service
.
files
.
modifyLabels
({
fileId
:
'
FILE_ID
'
,
resource
:
labelModificationRequest
,
});
return
updateResponse
;
}
catch
(
err
)
{
// TODO (developer) - Handle error
throw
err
;
}
```

Replace the following:

- LABEL_ID
: The
labelId
of the label to modify. To locate
the labels on a file, use the
files.listLabels
method.
- FILE_ID
: The
fileId
of the file for which the labels are
modified.
Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2026-04-20 UTC.


---

# Access link-shared Drive files using resource keys Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/guides/resource-keys

- Home
- Google Workspace
- Google Drive
- Guides
You can share Google Drive files and folders with others using the
Drive UI
or through the
Google Drive API
. When you share from
Drive, you can control whether people can edit, comment on, or
only open the file.

A
resource key
helps protect your file from unintended access. Resource keys
are an additional parameter that are passed so users can access certain files
that have been shared using a link. Users who haven't viewed the file before
must provide the resource key to gain access. Those who have recently viewed the
file, or have direct access, don't need the resource key to access the file.

A Drive file that's shared with a link can only be discovered by
users that can access the file as a result of a
type=user
or
type=group
permissions
resource. Requests from users
that only have access to these link-shared files using a
type=domain
or
type=anyone
permission might require a resource key.

For more information about permissions, see
Share files, folders and drives
. For a complete list of roles and the operations
permitted by each, see
Roles & permissions
.


## Read the resource key from the file

The Drive API returns a file's resource key on the read-only
resourceKey
field of the
files
resource.

If the file is a
Drive shortcut
, the
resource key for the shortcut target is returned on the read-only
shortcutDetails.targetResourceKey
field.

Fields in the
files
resource that return URLs,
such as
exportLinks
,
webContentLink
, and
webViewLink
, also include the
resourceKey
. Clients that integrate with the Drive UI can also
use
resourceKeys
within the
state
parameter. For more information, see
Download and export
files
.


## Set the resource key on the request

Resource keys for any files referenced by requests to the Drive API
are set on the
X-Goog-Drive-Resource-Keys
HTTP header.

Requests to the Drive API can specify one or more resource keys with
the
X-Goog-Drive-Resource-Keys
HTTP header.


### Syntax

A file ID and resource key pair are set on the header using a forward slash
(
/
) separator. The header is built by combining all the file ID and resource
key pairs using comma (
,
) separators.

For example, consider a request to move file
fileId1
from folder
fileId2
to
folder
fileId3
. Assume the resource keys for these three files are
resourceKey1
,
resourceKey2
, and
resourceKey3
, respectively. The header
built from these values using a forward slash and comma separators is:


```
X-Goog-Drive-Resource-Keys: fileId1/resourceKey1,fileId2/resourceKey2,fileId3/resourceKey3
```


### Related topics

- Share files, folders and drives
- Download and export files
- Protect file content
- Configure a Drive UI integration
Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2026-04-20 UTC.


---

# Search for files and folders Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/guides/search-files

- Home
- Google Workspace
- Google Drive
- Guides
This guide explains how the Google Drive API supports several ways to search files
and folders.

You can use the
list
method on the
files
resource to return all or some of a
Drive user's files and folders. The
list
method can also be
used to retrieve the
fileId
required for some resource methods (such as the
get
method and the
update
) method.


## Use the fields parameter

If you want to specify the fields to return in the response, you can set the
fields
system
parameter
with any method of the
files
resource. If you omit the
fields
parameter, the
server returns a default set of fields specific to the method. For example, the
list
method returns only the
kind
,
id
,
name
,
mimeType
, and
resourceKey
fields for each file. To return different
fields, see
Return specific fields
.


## Get a file

To get a file, use the
get
method on the
files
resource with the
fileId
path parameter.
If you don't know the file ID, you can
list all files
using the
list
method.

The method returns the file as an instance of a
files
resource. If you provide
the
alt=media
parameter, then the response includes the file contents in the
response body. To download a blob file, see
Download blob file content
.

To acknowledge the risk of downloading known malware or other
abusive
files, set the
acknowledgeAbuse
query parameter to
true
. This field is only applicable when
the
alt=media
parameter is set and the user is either the file owner or an
organizer of the shared drive in which the file resides.


## Search for all files and folders on the current user's My Drive

Use the
list
method without any parameters to return all files and folders.


```bash
GET https://www.googleapis.com/drive/v3/files
```


## Search for specific files or folders on the current user's My Drive

To search for a specific set of files or folders, use the query string
q
field
with the
list
method to filter the files to
return by combining one or more search terms.

The query string syntax contains the following three parts:

query_term operator values

Where:

- query_term
is the query term or field to search upon.
query_term
is the query term or field to search upon.

- operator
specifies the condition for the query term.
operator
specifies the condition for the query term.

- values
are the specific values you want to use to filter your search
results.
values
are the specific values you want to use to filter your search
results.

For example, the following query string filters the search to only return
folders by setting the
MIME type
:


```
q: mimeType = 'application/vnd.google-apps.folder'
```

To view all file query terms, see
File-specific query terms
.

To view all query operators that you can use to construct a query, see
Query
operators
.


### Query string examples

The following table lists examples of some basic query strings. The actual code
differs depending on the client library you use for your search.

You must also escape special characters in your file names to make sure the
query works correctly. For example, if a filename contains both an apostrophe
(
'
) and a backslash (
"\"
) character, use a backslash to escape them:
name
contains 'quinn\'s paper\\essay'
.


| What you want to query | Example |
| --- | --- |
| Files with the name "hello" | name = 'hello' |
| Files with a name containing the words "hello" and "goodbye" | name contains 'hello' and name contains 'goodbye' |
| Files with a name that does not contain the word "hello" | not name contains 'hello' |
| Files that contain the text "important" and in the trash | fullText contains 'important' and trashed = true |
| Files that contain the word "hello" | fullText contains 'hello' |
| Files that don't have the word "hello" | not fullText contains 'hello' |
| Files that contain the exact phrase "hello world" | fullText contains '"hello world"' |
| Files with a query that contains the "\" character (for example, "\authors") | fullText contains '\\authors' |
| Files that are folders | mimeType = 'application/vnd.google-apps.folder' |
| Files that are not folders | mimeType != 'application/vnd.google-apps.folder' |
| Files modified after a given date (default time zone is UTC) | modifiedTime > '2012-06-04T12:00:00' |
| Image or video files modified after a specific date | modifiedTime > '2012-06-04T12:00:00' and (mimeType contains 'image/' or mimeType contains 'video/') |
| Files that are starred | starred = true |
| Files within a collection (for example, the folder ID in the
parents
collection) | '1234567' in parents |
| Files in an
application data folder
in a collection | 'appDataFolder' in parents |
| Files for which user "test@example.org" is the owner | 'test@example.org' in owners |
| Files for which user "test@example.org" has write permission | 'test@example.org' in writers |
| Files for which members of the group "group@example.org" have write permission | 'group@example.org' in writers |
| Files shared with the authorized user with "hello" in the name | sharedWithMe and name contains 'hello' |
| Files with a custom file property visible to all apps | properties has { key='mass' and value='1.3kg' } |
| Files with a custom file property private to the requesting app | appProperties has { key='additionalID' and value='8e8aceg2af2ge72e78' } |
| Files that have not been shared with anyone or domains (only private, or shared with specific users or groups) | visibility = 'limited' |


### Filter search results with a client library

The following code sample shows how to use a client library to filter search
results to file names and IDs of JPEG files. This sample uses the
mimeType
query term to narrow results to files of type
image/jpeg
. It also sets
spaces
to
drive
to further narrow the search to the
Drive
space
. When
nextPageToken
returns
null
,
there are no more results.


### Java


```
import
com.google.api.client.http.HttpRequestInitializer
;
import
com.google.api.client.http.javanet.NetHttpTransport
;
import
com.google.api.client.json.gson.GsonFactory
;
import
com.google.api.services.drive.Drive
;
import
com.google.api.services.drive.DriveScopes
;
import
com.google.api.services.drive.model.File
;
import
com.google.api.services.drive.model.FileList
;
import
com.google.auth.http.HttpCredentialsAdapter
;
import
com.google.auth.oauth2.GoogleCredentials
;
import
java.io.IOException
;
import
java.util.ArrayList
;
import
java.util.Arrays
;
import
java.util.List
;
/* Class to demonstrate use-case of search files. */
public
class
SearchFile
{
/**
* Search for specific set of files.
*
* @return search result list.
* @throws IOException if service account credentials file not found.
*/
public
static
List<File>
searchFile
()
throws
IOException
{
/*Load pre-authorized user credentials from the environment.
TODO(developer) - See https://developers.google.com/identity for
guides on implementing OAuth2 for your application.*/
GoogleCredentials
credentials
=
GoogleCredentials
.
getApplicationDefault
()
.
createScoped
(
Arrays
.
asList
(
DriveScopes
.
DRIVE_FILE
));
HttpRequestInitializer
requestInitializer
=
new
HttpCredentialsAdapter
(
credentials
);
// Build a new authorized API client service.
Drive
service
=
new
Drive
.
Builder
(
new
NetHttpTransport
(),
GsonFactory
.
getDefaultInstance
(),
requestInitializer
)
.
setApplicationName
(
"Drive samples"
)
.
build
();
List<File>
files
=
new
ArrayList<File>
();
String
pageToken
=
null
;
do
{
FileList
result
=
service
.
files
().
list
()
.
setQ
(
"mimeType='image/jpeg'"
)
.
setSpaces
(
"drive"
)
.
setFields
(
"nextPageToken, files(id, title)"
)
.
setPageToken
(
pageToken
)
.
execute
();
for
(
File
file
:
result
.
getFiles
())
{
System
.
out
.
printf
(
"Found file: %s (%s)\n"
,
file
.
getName
(),
file
.
getId
());
}
files
.
addAll
(
result
.
getFiles
());
pageToken
=
result
.
getNextPageToken
();
}
while
(
pageToken
!=
null
);
return
files
;
}
}
```


### Python


```
import
google.auth
from
googleapiclient.discovery
import
build
from
googleapiclient.errors
import
HttpError
def
search_file
():
"""Search file in drive location
Load pre-authorized user credentials from the environment.
TODO(developer) - See https://developers.google.com/identity
for guides on implementing OAuth2 for the application.
"""
creds
,
_
=
google
.
auth
.
default
()
try
:
# create drive api client
service
=
build
(
"drive"
,
"v3"
,
credentials
=
creds
)
files
=
[]
page_token
=
None
while
True
:
# pylint: disable=maybe-no-member
response
=
(
service
.
files
()
.
list
(
q
=
"mimeType='image/jpeg'"
,
spaces
=
"drive"
,
fields
=
"nextPageToken, files(id, name)"
,
pageToken
=
page_token
,
)
.
execute
()
)
for
file
in
response
.
get
(
"files"
,
[]):
# Process change
print
(
f
'Found file:
{
file
.
get
(
"name"
)
}
,
{
file
.
get
(
"id"
)
}
'
)
files
.
extend
(
response
.
get
(
"files"
,
[]))
page_token
=
response
.
get
(
"nextPageToken"
,
None
)
if
page_token
is
None
:
break
except
HttpError
as
error
:
print
(
f
"An error occurred:
{
error
}
"
)
files
=
None
return
files
if
__name__
==
"__main__"
:
search_file
()
```


### Node.js


```
import
{
GoogleAuth
}
from
'google-auth-library'
;
import
{
google
}
from
'googleapis'
;
/**
* Searches for files in Google Drive.
* @return {Promise<object[]>} A list of files.
*/
async
function
searchFile
()
{
// Authenticate with Google and get an authorized client.
// TODO (developer): Use an appropriate auth mechanism for your app.
const
auth
=
new
GoogleAuth
({
scopes
:
'https://www.googleapis.com/auth/drive'
,
});
// Create a new Drive API client (v3).
const
service
=
google
.
drive
({
version
:
'v3'
,
auth
});
// Search for files with the specified query.
const
result
=
await
service
.
files
.
list
({
q
:
"mimeType='image/jpeg'"
,
fields
:
'nextPageToken, files(id, name)'
,
spaces
:
'drive'
,
});
// Print the name and ID of each found file.
(
result
.
data
.
files
??
[]).
forEach
((
file
)
=
>
{
console
.
log
(
'Found file:'
,
file
.
name
,
file
.
id
);
});
return
result
.
data
.
files
??
[];
}
```


### PHP


```
<
?php
use Google\Client;
use Google\Service\Drive;
function searchFiles()
{
try {
$client = new Client();
$client->useApplicationDefaultCredentials();
$client->addScope(Drive::DRIVE);
$driveService = new Drive($client);
$files = array();
$pageToken = null;
do {
$response = $driveService->files->listFiles(array(
'q' => "mimeType='image/jpeg'",
'spaces' => 'drive',
'pageToken' => $pageToken,
'fields' => 'nextPageToken, files(id, name)',
));
foreach ($response->files as $file) {
printf("Found file: %s (%s)\n", $file->name, $file->id);
}
array_push($files, $response->files);
$pageToken = $response->pageToken;
} while ($pageToken != null);
return $files;
} catch(Exception $e) {
echo "Error Message: ".$e;
}
}
```


## Search for files with a custom file property

To search for files with a custom file property, use either the
properties
or
the
appProperties
search query term with a key and value. For example, to
search for a custom file property that's private to the requesting app called
additionalID
with a value of
8e8aceg2af2ge72e78
:


```
appProperties has { key='additionalID' and value='8e8aceg2af2ge72e78' }
```

For more information, see
Add custom file
properties
.


## Search for files with a specific label or field value

To search for files with specific labels, use the
labels
search query term
with a specific label ID. For example:
'labels/
LABEL_ID
' in
labels
. If successful, the response body contains all file instances where the
label's applied.

To search for files without a specific label ID:
Not
'labels/
LABEL_ID
' in labels
.

You can also search for files based on specific field values. For example, to
search for files with a text value:
labels/
LABEL_ID
.text_field_id ='
TEXT
'
.

For more information, see
Search for files with a specific label or field
value
.


## Search the corpora

By default, the
user
item collection is set on the
corpora
query parameter
when the
list
method is used. To search other
item collections, such as those shared with a
domain
, you must explicitly set
the
corpora
parameter.

You can search multiple corpora in a single query; however, if the combined
corpora is too large, the API might return incomplete results. Check the
incompleteSearch
field in the response body. If it's
true
, then some documents were omitted. To
resolve this, narrow the
corpora
to use either
user
or
drive
.

When using the
orderBy
query
parameter on the
list
method, avoid using the
createdTime
key for queries on
large item collections as it requires additional processing and it might result
in timeouts or other issues. For time-related sorting on large item collections,
you can use
modifiedTime
instead as it's optimized to handle these queries.
For example,
?orderBy=modifiedTime
.

If you omit the
orderBy
query parameter, there's no default sort order and the
items are returned arbitrarily.


## Related topics

- Search for shared drives
- Search query terms and operators
- Google Workspace and Google Drive supported MIME types
- Roles and permissions
- Search for files with a specific label or field value
Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2026-05-07 UTC.


---

# Search for files with a specific label or field value Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/guides/search-labels

- Home
- Google Workspace
- Google Drive
- Guides
This page describes how to search for files with a specific label or field value
applied.


## Label field types

Google Drive label fields are strongly typed with each type supporting
different indexing and search semantics. The following table shows the available
data types.


| Type | Label type options | Supported search operators |
| --- | --- | --- |
| Text | TextOptions | is null, is not null, =, contains, starts with |
| Integer | IntegerOptions | is null, is not null, =, !=, <, >, <=, >= |
| Date | DateOptions | is null, is not null, =, !=, <, >, <=, >= |
| Selection | SelectionOptions | is null, is not null, =, != |
| User | UserOptions | is null, is not null, =, != |
| Selection List | SelectionOptions (with max_entries > 1) | is null, is not null, in, not in |
| User List | UserOptions (with max_entries > 1) | is null, is not null, in, not in |


### Search examples

1. Search based on the presence of a label or field

You can search for items where a specific label has (or has not) been applied:

- 'labels/contract' in labels
- not 'labels/contract' in labels
You can also search for items where a specific field has (or has not) been set:

- labels/contract.comment IS NOT NULL
- labels/contract.comment IS NULL
2. Search based on single-valued fields

You can write search queries to match expected field values. The following table
shows the valid field queries:


| What you want to query | Query string |
| --- | --- |
| Items where comment is set to "hello" | labels/contract.comment = 'hello' |
| Files where comment starts with "hello" | labels/contract.comment STARTS WITH 'hello' |
| Files where status is executed | labels/contract.status = 'executed' |
| Files where status is not executed | labels/contract.status != 'executed' |
| Files where execution_date is before a specific date | labels/contract.execution_date < '2020-06-22' |
| Files where value_usd (integer) is less than a specific value | labels/contract.value_usd < 2000 |
| Files where client_contact is set to a specific email address | labels/contract.client_contact = 'alex@altostrat.com' |

3. Search based on fields with multivalued fields (such as
ListOptions.max_entries > 1)

Fields that support multiple values can only be queried using the IN operator:

- '
EMAIL_ADDRESS
' IN labels/project.project_leads
- NOT '
EMAIL_ADDRESS
' IN labels/project.project_leads

## Example

The following code sample shows how to use one or more
labelId
to list all
files with a specific label or field value from a Drive
file
resource
. It also uses the
files.list
method. The request body must
be empty.

If you want to include
labelInfo
in the response, you also must specify:

- includeLabels
as a comma-separated list of IDs.
includeLabels
as a comma-separated list of IDs.

- labelInfo
in the
fields
parameter to denote that you want the
labelInfo
returned within
includeLabels
.
labelInfo
in the
fields
parameter to denote that you want the
labelInfo
returned within
includeLabels
.

If successful, the
response
body
contains the list
of files.


### Java


```
List<File>
fileList
=
driveService
.
files
().
list
().
setIncludeLabels
(
"
LABEL_1_ID
,
LABEL_2_ID
"
).
setFields
(
"items(labelInfo, id)"
).
setQ
(
"'labels/
LABEL_1_ID
' in labels and 'labels/
LABEL_2_ID
' in labels"
).
execute
().
getItems
();
```


### Python


```
file_list
=
drive_service
.
files
()
.
list
(
includeLabels
=
"
LABEL_1_ID
,
LABEL_2_ID
"
,
q
=
"'labels/
LABEL_1_ID
' in labels and 'labels/
LABEL_2_ID
' in labels"
,
fields
=
"items(labelInfo, id)"
)
.
execute
();
```


### Node.js


```
/**
* Search for Drive files with specific labels
* @return{obj} file list with labelInfo
**/
async
function
searchForFileWithLabels
()
{
// Get credentials and build service
// TODO (developer) - Use appropriate auth mechanism for your app
const
{
GoogleAuth
}
=
require
(
'google-auth-library'
);
const
{
google
}
=
require
(
'googleapis'
);
const
auth
=
new
GoogleAuth
({
scopes
:
'https://www.googleapis.com/auth/drive'
});
const
service
=
google
.
drive
({
version
:
'v3'
,
auth
});
try
{
const
fileList
=
await
service
.
files
.
list
({
includeLabels
:
'
LABEL_1_ID
,
LABEL_2_ID
'
,
q
:
'\'labels/
LABEL_1_ID
\' in labels and \'labels/
LABEL_2_ID
\' in labels'
,
fields
:
'files(labelInfo, id)'
,
});
return
file
;
}
catch
(
err
)
{
// TODO (developer) - Handle error
throw
err
;
}
```

Replace the following:

- LABEL_1_ID
: The first
labelId
of a label to return.
- LABEL_2_ID
: The second
labelId
of a label to return.
Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2026-04-20 UTC.


---

# Search for shared drives Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/guides/search-shareddrives

- Home
- Google Workspace
- Google Drive
- Guides
To search for a specific set of shared drives, use the query string
q
field
with
drives.list
to filter the drives to
return by combining one or more search terms.

A query string contains the following three parts:

query_term operator values

Where:

- query_term
is the query term or field to search upon.
query_term
is the query term or field to search upon.

- operator
specifies the condition for the query term.
operator
specifies the condition for the query term.

- values
are the specific values you want to use to filter your search
results.
values
are the specific values you want to use to filter your search
results.

To view the query terms and operators that you can use to filter shared drives,
see
Search query terms and operators
.

For example, the following query string filters the search to only return shared
drives with the name "Google Drive API resources."


```
q: name = 'Google Drive API resources' & useDomainAdminAccess=false
```


## Query string examples

The following table lists examples of some basic query strings for shared
drives. The actual code differs depending on the client library you use for your
search.

You must also escape special characters in your file names to make sure the
query works correctly. For example, if a filename contains both an apostrophe
(
'
) and a backslash (
"\"
) character, use a backslash to escape them:
name
contains 'quinn\'s paper\\essay'
.


| What you want to query | Example | useDomainAdminAccess
setting |
| --- | --- | --- |
| Shared drives created after June 1, 2017 | createdTime > '2017-06-01T12:00:00' | true |
| Shared drives visible in the default view | hidden = false | false |
| Shared drives with more than one member | memberCount > 1 | true |
| Shared drives with the word 'confidential' in the title and 20 or more members | name contains 'confidential' and memberCount >= 20 | true |
| Shared drives with the word 'confidential' in the title among all shared drives of the organization | name contains 'confidential' and orgUnitId = 'C03az79cb' | true |
| Shared drives with the word 'confidential' in the title among all shared drives that the user is a member of | name contains 'confidential' | false |
| Shared drives with no assigned organizer | organizerCount = 0 | true |
| Shared drives that don't contain the organizational unit ID | orgUnitId != 'C03az79cb' | true |


## Query multiple terms with parentheses

You can use parentheses to group multiple query terms together. For example, to
search for shared drives created after a specific date and that either have more
than five organizers or more than 20 members, use this query:


```
createdTime > '2019-01-01T12:00:00' and (organizerCount > 5 or
memberCount > 20)
```

This search returns all shared drives created after January 1st, 2019 and that
have more than five organizers or more than 20 members.

The Drive API evaluates
and
and
or
operators from left to right,
so the same search without parentheses would return:

- Only shared drives with more than five organizers that were created after
January 1st, 2019.
- All shared drives with more than 20 members, even those created before
January 1st, 2019.

## Related topics

- Search for files and folders
- Search query terms and operators
Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2026-04-20 UTC.


---

# Set a label field on a file Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/guides/set-label

- Home
- Google Workspace
- Google Drive
- Guides
This page describes how to set a label
Field
on a single
Google Drive file.

To add metadata to a file by setting a file label, use the
files.modifyLabels
method. The
request body
contains an instance of
ModifyLabelsRequest
to modify the set of labels on a file. The request might contain several
modifications that are applied atomically. That is, if any modifications aren't
valid, then the entire update is unsuccessful and none of the (potentially
dependent) changes are applied.

The
ModifyLabelsRequest
contains an instance of
LabelModification
which is a modification to a label on a file. It might also contain an instance
of
FieldModification
which is a modification to a label's field.

If successful, the
response
body
contains
the labels added or updated by the request. These exist within a
modifiedLabels
object of type
Label
.


## Example

The following code sample shows how to use the
fieldId
of a text field to set
a value for this
Field
on a
file. When a label
Field
is initially set on a file, it applies the label to
the file. You can then unset a single field or remove all fields associated with
the label. For more information, see
Unset a label field on a
file
and
Remove a label from a
file
.


### Java


```
LabelFieldModification
fieldModification
=
new
LabelFieldModification
().
setFieldId
(
"
FIELD_ID
"
).
setSetTextValues
(
ImmutableList
.
of
(
"
VALUE
"
));
ModifyLabelsRequest
modifyLabelsRequest
=
new
ModifyLabelsRequest
()
.
setLabelModifications
(
ImmutableList
.
of
(
new
LabelModification
()
.
setLabelId
(
"
LABEL_ID
"
)
.
setFieldModifications
(
ImmutableList
.
of
(
fieldModification
))));
ModifyLabelsResponse
modifyLabelsResponse
=
driveService
.
files
().
modifyLabels
(
"
FILE_ID
"
,
modifyLabelsRequest
).
execute
();
```


### Python


```
field_modification
=
{
'fieldId'
:
'
FIELD_ID
'
,
'setTextValues'
:[
'
VALUE
'
]}
label_modification
=
{
'labelId'
:
'
LABEL_ID
'
,
'fieldModifications'
:[
field_modification
]}
modified_labels
=
drive_service
.
files
()
.
modifyLabels
(
fileId
=
"
FILE_ID
"
,
body
=
{
'labelModifications'
:
[
label_modification
]})
.
execute
()
```


### Node.js


```
/**
* Set a label with a text field on a Drive file
* @return{obj} updated label data
**/
async
function
setLabelTextField
()
{
// Get credentials and build service
// TODO (developer) - Use appropriate auth mechanism for your app
const
{
GoogleAuth
}
=
require
(
'google-auth-library'
);
const
{
google
}
=
require
(
'googleapis'
);
const
auth
=
new
GoogleAuth
({
scopes
:
'https://www.googleapis.com/auth/drive'
});
const
service
=
google
.
drive
({
version
:
'v3'
,
auth
});
const
fieldModification
=
{
'fieldId'
:
'
FIELD_ID
'
,
'setTextValues'
:
[
'
VALUE
'
],
};
const
labelModification
=
{
'labelId'
:
'
LABEL_ID
'
,
'fieldModifications'
:
[
fieldModification
],
};
const
labelModificationRequest
=
{
'labelModifications'
:
[
labelModification
],
};
try
{
const
updateResponse
=
await
service
.
files
.
modifyLabels
({
fileId
:
'
FILE_ID
'
,
resource
:
labelModificationRequest
,
});
return
updateResponse
;
}
catch
(
err
)
{
// TODO (developer) - Handle error
throw
err
;
}
}
```

Replace the following:

- FIELD_ID
: The
fieldId
of the field to modify. To locate
the
fieldId
, retrieve the label using the
Google Drive Labels API
.
- VALUE
: The new
value
for this field.
- LABEL_ID
: The
labelId
of the label to modify.
- FILE_ID
: The
fileId
of the file for which the labels are
modified.

## Notes

- To set a label with no fields, apply
labelModifications
with no
fieldModifications
present.
- To set values for selection field options, use the
Choice
id of the value
that you can get by fetching the label schema in the
Drive Labels API
.
- Only a
Field
that supports lists of values can have multiple values set,
otherwise you'll receive a
400: Bad Request
error response.
- Set the proper value type for the selected
Field
(such as integer, text,
user, etc.), otherwise you'll receive a
400: Bad Request
error response.
You can retrieve the field data type using the
Drive Labels API
.
Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2026-04-20 UTC.


---

# Shared drive versus My Drive API differences Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/guides/shared-drives-diffs

- Home
- Google Workspace
- Google Drive
- Reference
Shared drives follow different organization, sharing, and ownership models from
a My Drive. As such, some My Drive operations
aren't permitted for content in a shared drive.

This guide outlines shared drive-specific API differences in the
files
and
changes
resources.


## File resource

The following fields in the
files
resource are
only populated for files located within a shared drive:

- hasAugmentedPermissions
: Whether any users are granted file access
directly on this file.
- capabilities/canAddFolderFromAnotherDrive
: Whether the current user can
add a folder from another drive (a different shared drive or My
Drive) to this folder.
- capabilities/canDeleteChildren
: Whether the current user can delete
children of this folder.
- capabilities/canMoveChildrenOutOfDrive
: Whether the current user can move
children of this folder outside of the shared drive.
- capabilities/canMoveChildrenWithinDrive
: Whether the current user can move
children of this folder within the shared drive.
- capabilities/canMoveItemWithinDrive
: Whether the current user can move
this shared drive item within the shared drive.
- capabilities/canReadDrive
: Whether the current user has read access to the
shared drive to which this file belongs.
- capabilities/canTrashChildren
: Whether the current user can trash children
of this folder.
- driveId
: The ID of the shared drive where the file is located.
- trashingUser
: If the file has been explicitly trashed, the user who
trashed it.
- trashedTime
: The time that the item was trashed. If you're using the older
Drive API v2, this field is called
trashedDate
.
The following fields aren't populated for files located within a shared drive:

- permissions
: Due to the potential size of shared drive access control
lists (ACLs), permissions aren't returned as part of files. Use the
permissions.list
method, which supports pagination, to list permissions
for a file within a shared drive or the shared drive folder.
- owners
,
ownerNames
,
ownedByMe
: Files within a shared drive are owned
by the shared drive, not individual users.
- folderColorRgb
: Folders cannot be colored individually.
- shared
: All items in a shared drive are shared.
- writersCanShare
: It's not possible to restrict sharing by role in shared
drives.
The following fields are only set when the user has been granted file access
permissions on an item:

- sharedWithMeDate
- sharingUser
The following fields require special consideration when you use them with shared
drives:

- parents.isRoot
: This field is only true for the My Drive
root folder; it's false for the shared drive top-level folder.
- parents
: A parent doesn't appear in the parents list if the requesting
user isn't a member of the shared drive and doesn't have access to the
parent. In addition, with the exception of the top level folder, the parents
list must contain exactly one item if the file is located within a shared
drive.
parents
: A parent doesn't appear in the parents list if the requesting
user isn't a member of the shared drive and doesn't have access to the
parent. In addition, with the exception of the top level folder, the parents
list must contain exactly one item if the file is located within a shared
drive.

- capabilities/canRemoveChildren
: Use
capabilities/canDeleteChildren
or
capabilities/canTrashChildren
.
capabilities/canRemoveChildren
: Use
capabilities/canDeleteChildren
or
capabilities/canTrashChildren
.


## Change resource

The following new fields are available in the
changes
resource for a shared drive:

- changeType
: The change type. Possible values are
file
and
drive
.
- driveId
: The ID of the shared drive associated with this change.
- drive
: The updated state of the shared drive. Present if the
changeType
is
drive
and the user is still a member of the shared drive.
Additional changes might be required for applications that need to sync content
with shared drives or track activity. For details, see
Track changes for users
and shared drives
.


## Related topics

- Files and folders overview
- Changes and revisions overview
Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2026-04-20 UTC.


---

# Create a shortcut to a Drive file Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/guides/shortcuts

- Home
- Google Workspace
- Google Drive
- Guides
Shortcuts
are files that link to other files or folders on Google Drive.
Shortcuts have these characteristics:

- An
application/vnd.google-apps.shortcut
MIME type. For more information,
see
Google Workspace & Google Drive supported MIME
types
.
An
application/vnd.google-apps.shortcut
MIME type. For more information,
see
Google Workspace & Google Drive supported MIME
types
.

- The ACL for a shortcut inherits the ACL of the parent. The shortcut's ACL
cannot be changed directly.
The ACL for a shortcut inherits the ACL of the parent. The shortcut's ACL
cannot be changed directly.

- A
targetId
pointing to the target file or folder, also referred to as the
"target."
A
targetId
pointing to the target file or folder, also referred to as the
"target."

- A
targetMimeType
indicating the MIME type for the target. The
targetMimeType
is used to determine the type icon to display. The target's
MIME type is copied to the
targetMimeType
field when the shortcut is
created.
A
targetMimeType
indicating the MIME type for the target. The
targetMimeType
is used to determine the type icon to display. The target's
MIME type is copied to the
targetMimeType
field when the shortcut is
created.

- The
targetId
and
targetMimeType
fields are part of the
shortcutDetails
field within the
file
resource.
The
targetId
and
targetMimeType
fields are part of the
shortcutDetails
field within the
file
resource.

- A shortcut can only have one parent. If a shortcut file is required in other
Drive locations, the shortcut file can be copied to the
additional locations.
A shortcut can only have one parent. If a shortcut file is required in other
Drive locations, the shortcut file can be copied to the
additional locations.

- When the target is deleted, or when the current user loses access to the
target, the user's shortcut pointing to the target breaks.
When the target is deleted, or when the current user loses access to the
target, the user's shortcut pointing to the target breaks.

- The title of a shortcut can differ from the target. When a shortcut is
created, the title of the target is used as the title of the shortcut. After
creation, the shortcut's title and target's title can be changed
independently. If the target's name is changed, previously created shortcuts
retain the old title.
The title of a shortcut can differ from the target. When a shortcut is
created, the title of the target is used as the title of the shortcut. After
creation, the shortcut's title and target's title can be changed
independently. If the target's name is changed, previously created shortcuts
retain the old title.

- The MIME type of a shortcut can become stale. While rare, a blob file's MIME
type changes when a revision of a different type is uploaded, but any
shortcuts pointing to the updated file retain the original MIME type. For
example, if you upload a JPG file to Drive, then upload an
AVI revision, Drive identifies the change and updates the
thumbnail for the actual file. However, the shortcut continues to have a JPG
thumbnail.
The MIME type of a shortcut can become stale. While rare, a blob file's MIME
type changes when a revision of a different type is uploaded, but any
shortcuts pointing to the updated file retain the original MIME type. For
example, if you upload a JPG file to Drive, then upload an
AVI revision, Drive identifies the change and updates the
thumbnail for the actual file. However, the shortcut continues to have a JPG
thumbnail.

- In
Google Account Data
Export
also known as Google Takeout, shortcuts are represented as Netscape
bookmark files containing links to the target.
In
Google Account Data
Export
also known as Google Takeout, shortcuts are represented as Netscape
bookmark files containing links to the target.

For more information, see
Find files & folders with Google Drive
shortcuts
.


## Create a shortcut

To create a shortcut, set the MIME type to
application/vnd.google-apps.shortcut
, set the
targetId
to the file or folder
the shortcut should link to, and call
files.create
to create a shortcut.

The following examples show how to create a shortcut using a client library:


### Python


```
file_metadata
=
{
'name'
:
'
FILE_NAME
'
,
'mimeType'
:
'text/plain'
}
file
=
drive_service
.
files
()
.
create
(
body
=
file_metadata
,
fields
=
'id'
)
.
execute
()
print
(
'File ID:
%s
'
%
file
.
get
(
'id'
))
shortcut_metadata
=
{
'Name'
:
'
SHORTCUT_NAME
'
,
'mimeType'
:
'application/vnd.google-apps.shortcut'
,
'shortcutDetails'
:
{
'targetId'
:
file
.
get
(
'id'
)
}
}
shortcut
=
drive_service
.
files
()
.
create
(
body
=
shortcut_metadata
,
fields
=
'id,shortcutDetails'
)
.
execute
()
print
(
'File ID:
%s
, Shortcut Target ID:
%s
, Shortcut Target MIME type:
%s
'
%
(
shortcut
.
get
(
'id'
),
shortcut
.
get
(
'shortcutDetails'
)
.
get
(
'targetId'
),
shortcut
.
get
(
'shortcutDetails'
)
.
get
(
'targetMimeType'
)))
```


### Node.js


```
var
fileMetadata
=
{
'name'
:
'
FILE_NAME
'
,
'mimeType'
:
'text/plain'
};
drive
.
files
.
create
({
'resource'
:
fileMetadata
,
'fields'
:
'id'
},
function
(
err
,
file
)
{
if
(
err
)
{
// Handle error
console
.
error
(
err
);
}
else
{
console
.
log
(
'File Id: '
+
file
.
id
);
shortcutMetadata
=
{
'name'
:
'
SHORTCUT_NAME
'
,
'mimeType'
:
'application/vnd.google-apps.shortcut'
'shortcutDetails'
:
{
'targetId'
:
file
.
id
}
};
drive
.
files
.
create
({
'resource'
:
shortcutMetadata
,
'fields'
:
'id,name,mimeType,shortcutDetails'
},
function
(
err
,
shortcut
)
{
if
(
err
)
{
// Handle error
console
.
error
(
err
);
}
else
{
console
.
log
(
'Shortcut Id: '
+
shortcut
.
id
+
', Name: '
+
shortcut
.
name
+
', target Id: '
+
shortcut
.
shortcutDetails
.
targetId
+
', target MIME type: '
+
shortcut
.
shortcutDetails
.
targetMimeType
);
}
}
}
});
```

Replace the following:

- FILE_NAME
: the file name requiring a shortcut.
- SHORTCUT_NAME
: the name for this shortcut.
By default, the shortcut is created on the current user's My
Drive and shortcuts are only created for files or folders for
which the current user has access.


## Search for a shortcut

To search for a shortcut, use the query string
q
with
files.list
to filter the shortcuts to
return.

mimeType
operator values

Where:

- query_term
is the query term or field to search upon. To view the query
terms that can be used to filter shared drives, refer to
Search query
terms
.
- operator
specifies the condition for the query term. To view which
operators you can use with each query term, refer to
Query operators
.
- values
are the specific values you want to use to filter your search
results.
For example, the following query string filters the search to return all
shortcuts to spreadsheet files:


```
q: mimeType='application/vnd.google-apps.shortcut' AND shortcutDetails.targetMimeType='application/vnd.google-apps.spreadsheet'
```

Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2026-04-20 UTC.


---

# Create a shortcut file to content stored by your app Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/guides/third-party-shortcuts

- Home
- Google Workspace
- Google Drive
- Guides
Third-party shortcuts
in Google Drive are metadata-only files that link to
other files on external, third-party owned, storage systems. These shortcuts act
as reference links to the "content" files stored by an application outside of
Drive, usually in a different datastore or cloud storage system.

To create a third-party shortcut, use the
files.create
method of
the Google Drive API and set the MIME type to
application/vnd.google-apps.drive-sdk
. Don't upload any content when creating
the file. For more information, see
Google Workspace
and Google Drive supported MIME
types
.

You cannot upload or download third-party shortcuts.

The following code samples show how to create a third-party shortcut using a
client library:


### Java


```
import
com.google.api.client.googleapis.json.GoogleJsonResponseException
;
import
com.google.api.client.http.HttpRequestInitializer
;
import
com.google.api.client.http.javanet.NetHttpTransport
;
import
com.google.api.client.json.gson.GsonFactory
;
import
com.google.api.services.drive.Drive
;
import
com.google.api.services.drive.DriveScopes
;
import
com.google.api.services.drive.model.File
;
import
com.google.auth.http.HttpCredentialsAdapter
;
import
com.google.auth.oauth2.GoogleCredentials
;
import
java.io.IOException
;
import
java.util.Arrays
;
/* Class to demonstrate Drive's create shortcut use-case */
public
class
CreateShortcut
{
/**
* Creates shortcut for file.
*
* @throws IOException if service account credentials file not found.
*/
public
static
String
createShortcut
()
throws
IOException
{
/* Load pre-authorized user credentials from the environment.
TODO(developer) - See https://developers.google.com/identity for
guides on implementing OAuth2 for your application.*/
GoogleCredentials
credentials
=
GoogleCredentials
.
getApplicationDefault
()
.
createScoped
(
Arrays
.
asList
(
DriveScopes
.
DRIVE_FILE
));
HttpRequestInitializer
requestInitializer
=
new
HttpCredentialsAdapter
(
credentials
);
// Build a new authorized API client service.
Drive
service
=
new
Drive
.
Builder
(
new
NetHttpTransport
(),
GsonFactory
.
getDefaultInstance
(),
requestInitializer
)
.
setApplicationName
(
"Drive samples"
)
.
build
();
try
{
// Create Shortcut for file.
File
fileMetadata
=
new
File
();
fileMetadata
.
setName
(
"Project plan"
);
fileMetadata
.
setMimeType
(
"application/vnd.google-apps.drive-sdk"
);
File
file
=
service
.
files
().
create
(
fileMetadata
)
.
setFields
(
"id"
)
.
execute
();
System
.
out
.
println
(
"File ID: "
+
file
.
getId
());
return
file
.
getId
();
}
catch
(
GoogleJsonResponseException
e
)
{
// TODO(developer) - handle error appropriately
System
.
err
.
println
(
"Unable to create shortcut: "
+
e
.
getDetails
());
throw
e
;
}
}
}
```


### Python


```
import
google.auth
from
googleapiclient.discovery
import
build
from
googleapiclient.errors
import
HttpError
def
create_shortcut
():
"""Create a third party shortcut
Load pre-authorized user credentials from the environment.
TODO(developer) - See https://developers.google.com/identity
for guides on implementing OAuth2 for the application.
"""
creds
,
_
=
google
.
auth
.
default
()
try
:
# create drive api client
service
=
build
(
"drive"
,
"v3"
,
credentials
=
creds
)
file_metadata
=
{
"name"
:
"Project plan"
,
"mimeType"
:
"application/vnd.google-apps.drive-sdk"
,
}
# pylint: disable=maybe-no-member
file
=
service
.
files
()
.
create
(
body
=
file_metadata
,
fields
=
"id"
)
.
execute
()
print
(
f
'File ID:
{
file
.
get
(
"id"
)
}
'
)
except
HttpError
as
error
:
print
(
f
"An error occurred:
{
error
}
"
)
return
file
.
get
(
"id"
)
if
__name__
==
"__main__"
:
create_shortcut
()
```


### PHP


```
<
?php
use Google\Client;
use Google\Service\Drive;
use Google\Service\Drive\DriveFile;
function createShortcut()
{
try {
$client = new Client();
$client->useApplicationDefaultCredentials();
$client->addScope(Drive::DRIVE);
$driveService = new Drive($client);
$fileMetadata = new DriveFile(array(
'name' => 'Project plan',
'mimeType' => 'application/vnd.google-apps.drive-sdk'));
$file = $driveService->files->create($fileMetadata, array(
'fields' => 'id'));
printf("File ID: %s\n", $file->id);
return $file->id;
} catch(Exception $e) {
echo "Error Message: ".$e;
}
}
```


### .NET


```
using
Google.Apis.Auth.OAuth2
;
using
Google.Apis.Drive.v3
;
using
Google.Apis.Services
;
namespace
DriveV3Snippets
{
// Class to demonstrate Drive's create shortcut use-case
public
class
CreateShortcut
{
/// <summary>
/// Create a third party shortcut.
/// </summary>
/// <returns>newly created shortcut file id, null otherwise.</returns>
public
static
string
DriveCreateShortcut
()
{
try
{
/* Load pre-authorized user credentials from the environment.
TODO(developer) - See https://developers.google.com/identity for
guides on implementing OAuth2 for your application. */
GoogleCredential
credential
=
GoogleCredential
.
GetApplicationDefault
()
.
CreateScoped
(
DriveService
.
Scope
.
Drive
);
// Create Drive API service.
var
service
=
new
DriveService
(
new
BaseClientService
.
Initializer
{
HttpClientInitializer
=
credential
,
ApplicationName
=
"Drive API Snippets"
});
// Create Shortcut for file.
var
fileMetadata
=
new
Google
.
Apis
.
Drive
.
v3
.
Data
.
File
()
{
Name
=
"Project plan"
,
MimeType
=
"application/vnd.google-apps.drive-sdk"
};
var
request
=
service
.
Files
.
Create
(
fileMetadata
);
request
.
Fields
=
"id"
;
var
file
=
request
.
Execute
();
// Prints the shortcut file id.
Console
.
WriteLine
(
"File ID: "
+
file
.
Id
);
return
file
.
Id
;
}
catch
(
Exception
e
)
{
// TODO(developer) - handle error appropriately
if
(
e
is
AggregateException
)
{
Console
.
WriteLine
(
"Credential Not found"
);
}
else
{
throw
;
}
}
return
null
;
}
}
}
```


### Node.js


```
import
{
GoogleAuth
}
from
'google-auth-library'
;
import
{
google
}
from
'googleapis'
;
/**
* Creates a shortcut to a third-party resource.
* @return {Promise<string|null|undefined>} The shortcut ID.
*/
async
function
createShortcut
()
{
// Authenticate with Google and get an authorized client.
// TODO (developer): Use an appropriate auth mechanism for your app.
const
auth
=
new
GoogleAuth
({
scopes
:
'https://www.googleapis.com/auth/drive'
,
});
// Create a new Drive API client (v3).
const
service
=
google
.
drive
({
version
:
'v3'
,
auth
});
// The metadata for the new shortcut.
const
fileMetadata
=
{
name
:
'Project plan'
,
mimeType
:
'application/vnd.google-apps.drive-sdk'
,
};
// Create the new shortcut.
const
file
=
await
service
.
files
.
create
({
requestBody
:
fileMetadata
,
fields
:
'id'
,
});
// Print the ID of the new shortcut.
console
.
log
(
'File Id:'
,
file
.
data
.
id
);
return
file
.
data
.
id
;
}
```


## How third-party shortcuts work

When you create a third-party shortcut using the
files.create
method, it uses
a
POST
request to insert the metadata and create a shortcut to your app's
content:


```bash
POST https://www.googleapis.com/drive/v3/files
Authorization:
AUTHORIZATION_HEADER
{
  "title": "
FILE_TITLE
",
  "mimeType": "application/vnd.google-apps.drive-sdk"
}
```

When the third-party shortcut is clicked, the user is redirected to the external
site where the file is housed. The Drive file ID is contained in
the
state
parameter. For more
information, see
Handle an Open URL for app-specific
documents
.

The third-party app or website is then responsible for matching the file ID in
the
state
parameter to the content housed within their system.


## Add custom thumbnails and indexable text

To increase the discoverability of files associated with third-party shortcuts,
you can upload both thumbnail images and indexable text when inserting or
modifying the file metadata. For more information, see
Manage file metadata
.


## Related topics

- Create a shortcut to a Drive file
- Configure a Drive UI integration
- Google Workspace and Google Drive supported MIME types
Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2026-04-20 UTC.


---

# Transfer file ownership Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/guides/transfer-file

- Home
- Google Workspace
- Google Drive
- Guides
You own the files that you create or upload on Google Drive. You can transfer
ownership of these files to another account.


## Transfer file ownership to another Google Workspace account in the same organization

Ownership of files existing in "My Drive" can be transferred from
one
Google Workspace
account
to another account in the same organization. An organization that owns a shared
drive owns the files within it. Therefore, ownership transfers are not supported
for files and folders in shared drives. Organizers of a shared drive can move
items from that shared drive and into their own "My Drive" which
transfers the ownership to them.

To transfer ownership of a file in "My Drive", do one of the
following:

- Create
a file permission
granting a specific user (
type=user
) owner access (
role=owner
).
Create
a file permission
granting a specific user (
type=user
) owner access (
role=owner
).

- Update an existing file permission with
role=owner
and transfer ownership
to the specified user (
transferOwnership=true
).
Update an existing file permission with
role=owner
and transfer ownership
to the specified user (
transferOwnership=true
).


## Transfer file ownership from one consumer account to another

Ownership of files can be transferred between one
consumer
account
to another. However, Drive doesn't transfer ownership of a file
between the two consumer accounts until the prospective owner explicitly
consents to the transfer. To transfer file ownership from one consumer account
to another:

- The current owner initiates an ownership transfer by creating or updating
the prospective owner's file permission. The permission must include these
settings:
role=writer
,
type=user
, and
pendingOwner=true
. If the
current owner is creating a permission for the prospective owner, an email
notification is sent to the prospective owner indicating that they're being
asked to assume ownership of the file.
The current owner initiates an ownership transfer by creating or updating
the prospective owner's file permission. The permission must include these
settings:
role=writer
,
type=user
, and
pendingOwner=true
. If the
current owner is creating a permission for the prospective owner, an email
notification is sent to the prospective owner indicating that they're being
asked to assume ownership of the file.

- The prospective owner accepts the ownership transfer request by creating or
updating their file permission. The permission must include these settings:
role=owner
and
transferOwnership=true
. If the prospective owner is
creating a new permission, an email notification is sent to the previous
owner indicating that ownership has been transferred.
The prospective owner accepts the ownership transfer request by creating or
updating their file permission. The permission must include these settings:
role=owner
and
transferOwnership=true
. If the prospective owner is
creating a new permission, an email notification is sent to the previous
owner indicating that ownership has been transferred.

When a file is transferred, the previous owner's role is downgraded to
writer
.


## Related topics

- Share files, folders, and drives
Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2026-04-20 UTC.


---

# Unset a label field on a file Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/guides/unset-label

- Home
- Google Workspace
- Google Drive
- Guides
This page describes how to unset a label
Field
on a single
Google Drive file.

To remove metadata from a file by unsetting a file label, use the
files.modifyLabels
method. The
request body
contains an instance of
ModifyLabelsRequest
to modify the set of labels on a file. The request might contain several
modifications that are applied atomically. That is, if any modifications aren't
valid, then the entire update is unsuccessful and none of the (potentially
dependent) changes are applied.

The
ModifyLabelsRequest
contains an instance of
LabelModification
which is a modification to a label on a file. It might also contain an instance
of
FieldModification
which is a modification to a label's field. To unset the values for the field,
set
FieldModification.unsetValues
to
True
.

If successful, the
response
body
contains
the labels added or updated by the request. These exist within a
modifiedLabels
object of type
Label
.


## Example

The following code sample shows how to use the
fieldId
and
labelId
to unset
the field values on the associated
fileId
. For example, if a label contains
both text and user fields, unsetting the text field removes it from the label
but leaves the user field untouched. Whereas removing a label deletes
both
the
text and user fields associated with the label. For more information, see
Remove a label from a file
.


### Java


```
LabelFieldModification
fieldModification
=
new
LabelFieldModification
().
setFieldId
(
"
FIELD_ID
"
).
setUnsetValues
(
true
);
ModifyLabelsRequest
modifyLabelsRequest
=
new
ModifyLabelsRequest
()
.
setLabelModifications
(
ImmutableList
.
of
(
new
LabelModification
()
.
setLabelId
(
"
LABEL_ID
"
)
.
setFieldModifications
(
ImmutableList
.
of
(
fieldModification
))));
ModifyLabelsResponse
modifyLabelsResponse
=
driveService
.
files
().
modifyLabels
(
"
FILE_ID
"
,
modifyLabelsRequest
).
execute
();
```


### Python


```
field_modification
=
{
'fieldId'
:
'
FIELD_ID
'
,
'unsetValues'
:
True
}
label_modification
=
{
'labelId'
:
'
LABEL_ID
'
,
'fieldModifications'
:[
field_modification
]}
modified_labels
=
drive_service
.
files
()
.
modifyLabels
(
fileId
=
"
FILE_ID
"
,
body
=
{
'labelModifications'
:
[
label_modification
]})
.
execute
();
```


### Node.js


```
/**
* Unset a label with a field on a Drive file
* @return{obj} updated label data
**/
async
function
unsetLabelField
()
{
// Get credentials and build service
// TODO (developer) - Use appropriate auth mechanism for your app
const
{
GoogleAuth
}
=
require
(
'google-auth-library'
);
const
{
google
}
=
require
(
'googleapis'
);
const
auth
=
new
GoogleAuth
({
scopes
:
'https://www.googleapis.com/auth/drive'
});
const
service
=
google
.
drive
({
version
:
'v3'
,
auth
});
const
fieldModification
=
{
'fieldId'
:
'
FIELD_ID
'
,
'unsetValues'
:
True
,
};
const
labelModification
=
{
'labelId'
:
'
LABEL_ID
'
,
'fieldModifications'
:
[
fieldModification
],
};
const
labelModificationRequest
=
{
'labelModifications'
:
[
labelModification
],
};
try
{
const
updateResponse
=
await
service
.
files
.
modifyLabels
({
fileId
:
'
FILE_ID
'
,
resource
:
labelModificationRequest
,
});
return
updateResponse
;
}
catch
(
err
)
{
// TODO (developer) - Handle error
throw
err
;
}
}
```

Replace the following:

- FIELD_ID
: The
fieldId
of the field to modify. To locate
the
fieldId
, retrieve the label using the
Google Drive Labels API
.
- LABEL_ID
: The
labelId
of the label to modify.
- FILE_ID
: The
fileId
of the file for which the labels are
modified.
Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2026-04-20 UTC.


---

# Return user info Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/guides/user-info

- Home
- Google Workspace
- Google Drive
- Guides
Google Drive provides two options to gather information about
Drive users:

- Using the
about
resource, you can retrieve
information about the user, the user's Drive settings, and
their system capabilities.
Using the
about
resource, you can retrieve
information about the user, the user's Drive settings, and
their system capabilities.

- Using the
apps
resource, you can retrieve a
list of the user's installed apps, with information about each app's
supported MIME types, file extensions, and other details.
Using the
apps
resource, you can retrieve a
list of the user's installed apps, with information about each app's
supported MIME types, file extensions, and other details.

This guide explains how you can retrieve user info in Drive.


## Get details about a user

To return information on a Drive user as an instance of
about
, use the
get
method. The returned values are measured
in bytes.

You
must
set the
fields
system
parameter
on
the
get
method to specify the fields to return in the response. In most
Drive methods this action is only required to return non-default
fields but it's mandatory for the
about
resource. If you omit the parameter,
the method returns an error. For more information, see
Return specific fields
.

The following code sample shows how to provide multiple
fields
as a query parameter in the request. The response returns the field values for the request.

Request


```bash
GET https://www.googleapis.com/drive/v3/about/?fields=kind,user,storageQuota
```

Response


```
{
  "kind": "drive#about",
  "user": {
    "kind": "drive#user",
    "displayName": "
DISPLAY_NAME
",
    "photoLink": "
PHOTO_LINK
",
    "me": true,
    "permissionId": "
PERMISSION_ID
",
    "emailAddress": "
EMAIL_ADDRESS
"
  },
  "storageQuota": {
    "usage": "10845031958",
    "usageInDrive": "2222008387",
    "usageInDriveTrash": "91566"
  }
}
```

The response includes the following values:

- DISPLAY_NAME
: the user's name in plain text.
- PHOTO_LINK
: the URL of the user's profile photo.
- PERMISSION_ID
: the user's ID within the
Permission
resources.
- EMAIL_ADDRESS
: the user's email address

## List user apps

Google Drive apps are listed in the
Google Workspace Marketplace
and
are used to make Drive more convenient such as the Google Docs
app or an add-on used within Docs to
sign documents. For more information, see
Use Google Drive
apps
.

To return a list of all the user's installed apps as an instance of
apps
, use the
list
method
without any parameters.

If you want to specify the fields to return in the response, you can set the
fields
system
parameter
. If
you don't specify the
fields
parameter, the server returns a default set of
fields. For more information, see
Return specific fields
.

The following code sample shows how to return a list of all the user's installed apps in the request. The response returns the field values for the request.


```bash
GET https://www.googleapis.com/drive/v3/apps
```


```
{
  "kind": "drive#appList",
  "selfLink": "https://www.googleapis.com/drive/v3/apps",
  "items": [
    {
      "kind": "drive#app",
      "id": "
ID
",
      "name": "Google Sheets",
      "supportsCreate": true,
      "supportsImport": true,
      "supportsMultiOpen": false,
      "supportsOfflineCreate": true,
      "productUrl": "https://chrome.google.com/webstore/detail/felcaaldnbdncclmgdcncolpebgiejap",
      "productId": "
PRODUCT_ID
"
    }
  ],
  "defaultAppIds": [
    "
ID
"
  ]
}
```

- ID
: the app ID.
- PRODUCT_ID
: the product listing ID for this app.

### List user apps with query parameters

To find a specific app, use one or more of the optional query parameters:

- appFilterExtensions
: Filter the search results using a comma-separated
list of file extensions. Apps within the app query scope that can open the
listed file extensions are included in the response. If
appFilterMimeTypes
are also provided, a union of the two resulting app lists is returned.
Examples of extensions include
docx
for Microsoft Word and
pptx
for
Microsoft PowerPoint. For more examples of file extensions, see
Export MIME
types for Google Workspace documents
.
The following code sample shows how to provide multiple file extensions as a
query parameter:
GET
https://www.googleapis.com/drive/v3/apps?appFilterExtensions=docx,pptx
.
appFilterExtensions
: Filter the search results using a comma-separated
list of file extensions. Apps within the app query scope that can open the
listed file extensions are included in the response. If
appFilterMimeTypes
are also provided, a union of the two resulting app lists is returned.
Examples of extensions include
docx
for Microsoft Word and
pptx
for
Microsoft PowerPoint. For more examples of file extensions, see
Export MIME
types for Google Workspace documents
.

The following code sample shows how to provide multiple file extensions as a
query parameter:
GET
https://www.googleapis.com/drive/v3/apps?appFilterExtensions=docx,pptx
.

- appFilterMimeTypes
: Filter the search results using a comma-separated list
of MIME types. Apps within the app query scope that can open the listed MIME
types are included in the response. If
appFilterExtensions
are also
provided, a union of the two resulting app lists is returned. Examples of
MIME types include
application/vnd.google-apps.form
for Google Forms and
application/vnd.google-apps.site
for Google Sites. For more examples of
MIME types, see
Google Workspace and Google Drive supported MIME
types
.
The following code sample shows how to provide multiple MIME types as a
query parameter:
GET
https://www.googleapis.com/drive/v3/apps?appFilterMimeTypes=application/vnd.google-apps.form,application/vnd.google-apps.site
.
appFilterMimeTypes
: Filter the search results using a comma-separated list
of MIME types. Apps within the app query scope that can open the listed MIME
types are included in the response. If
appFilterExtensions
are also
provided, a union of the two resulting app lists is returned. Examples of
MIME types include
application/vnd.google-apps.form
for Google Forms and
application/vnd.google-apps.site
for Google Sites. For more examples of
MIME types, see
Google Workspace and Google Drive supported MIME
types
.

The following code sample shows how to provide multiple MIME types as a
query parameter:
GET
https://www.googleapis.com/drive/v3/apps?appFilterMimeTypes=application/vnd.google-apps.form,application/vnd.google-apps.site
.

- languageCode
: Filter the search results using a language or locale code,
as defined by BCP 47, with some extensions from
Unicode's LDML
format
. Examples of language codes
include
en-us
for English (United States) and
fr-ca
for French (Canada).
The following code sample shows how to provide multiple language codes as a
query parameter:
GET
https://www.googleapis.com/drive/v3/apps?languageCode=en-us,fr-ca
.
languageCode
: Filter the search results using a language or locale code,
as defined by BCP 47, with some extensions from
Unicode's LDML
format
. Examples of language codes
include
en-us
for English (United States) and
fr-ca
for French (Canada).

The following code sample shows how to provide multiple language codes as a
query parameter:
GET
https://www.googleapis.com/drive/v3/apps?languageCode=en-us,fr-ca
.


## Get user app by ID

To download the detailed app info as an instance of
apps
, use the
get
method with the app ID.

The following code sample shows how to provide an
appId
as a query parameter in the request. The response returns the field values for the request.


```bash
GET https://www.googleapis.com/drive/v3/apps/
APP_ID
```


```
{
  "kind": "drive#app",
  "id": "
ID
",
  "name": "Google Sheets",
  "supportsCreate": true,
  "supportsImport": true,
  "supportsMultiOpen": false,
  "supportsOfflineCreate": true,
  "productUrl": "https://chrome.google.com/webstore/detail/felcaaldnbdncclmgdcncolpebgiejap",
  "productId": "
PRODUCT_ID
"
}
```


## Related topics

Here are a few next steps you might try:

- To create a file in Drive, see
Create and manage files
.
To create a file in Drive, see
Create and manage files
.

- To upload file data when you create or update a file, see
Upload file
data
.
To upload file data when you create or update a file, see
Upload file
data
.

- To download and export files, see
Download and export
files
.
To download and export files, see
Download and export
files
.

Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2026-04-20 UTC.


---

# Google Drive API Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/reference/rest/v3

- Home
- Google Workspace
- Google Drive
- Reference
The Google Drive API allows clients to access resources from Google Drive.

- REST Resource: v3.about
- REST Resource: v3.accessproposals
- REST Resource: v3.approvals
- REST Resource: v3.apps
- REST Resource: v3.changes
- REST Resource: v3.channels
- REST Resource: v3.comments
- REST Resource: v3.drives
- REST Resource: v3.files
- REST Resource: v3.operations
- REST Resource: v3.permissions
- REST Resource: v3.replies
- REST Resource: v3.revisions

## Service: googleapis.com/drive/v3

To call this service, we recommend that you use the Google-provided
client libraries
. If your application needs to use your own libraries to call this service, use the following information when you make the API requests.


### Discovery document

A
Discovery Document
is a machine-readable specification for describing and consuming REST APIs. It is used to build client libraries, IDE plugins, and other tools that interact with Google APIs. One service may provide multiple discovery documents. This service provides the following discovery document:

- https://www.googleapis.com/discovery/v1/apis/drive/v3/rest

### Service endpoint

A
service endpoint
is a base URL that specifies the network address of an API service. One service might have multiple service endpoints. This service has the following service endpoint and all URIs below are relative to this service endpoint:

- https://www.googleapis.com

## REST Resource:
v3.about


| Methods |  |
| --- | --- |
| get | GET /drive/v3/about
Gets information about the user, the user's Drive, and system capabilities. |


## REST Resource:
v3.accessproposals


| Methods |  |
| --- | --- |
| get | GET /drive/v3/files/{fileId}/accessproposals/{proposalId}
Retrieves an access proposal by ID. |
| list | GET /drive/v3/files/{fileId}/accessproposals
List the access proposals on a file. |
| resolve | POST /drive/v3/files/{fileId}/accessproposals/{proposalId}:resolve
Approves or denies an access proposal. |


## REST Resource:
v3.approvals


| Methods |  |
| --- | --- |
| approve | POST /drive/v3/files/{fileId}/approvals/{approvalId}:approve
Approves an approval. |
| cancel | POST /drive/v3/files/{fileId}/approvals/{approvalId}:cancel
Cancels an approval. |
| comment | POST /drive/v3/files/{fileId}/approvals/{approvalId}:comment
Comments on an approval. |
| decline | POST /drive/v3/files/{fileId}/approvals/{approvalId}:decline
Declines an approval. |
| get | GET /drive/v3/files/{fileId}/approvals/{approvalId}
Gets an approval by ID. |
| list | GET /drive/v3/files/{fileId}/approvals
Lists the approvals on a file. |
| reassign | POST /drive/v3/files/{fileId}/approvals/{approvalId}:reassign
Reassigns the reviewers on an approval. |
| start | POST /drive/v3/files/{fileId}/approvals:start
Starts an approval on a file. |


## REST Resource:
v3.apps


| Methods |  |
| --- | --- |
| get | GET /drive/v3/apps/{appId}
Gets a specific app. |
| list | GET /drive/v3/apps
Lists a user's installed apps. |


## REST Resource:
v3.changes


| Methods |  |
| --- | --- |
| getStartPageToken | GET /drive/v3/changes/startPageToken
Gets the starting pageToken for listing future changes. |
| list | GET /drive/v3/changes
Lists the changes for a user or shared drive. |
| watch | POST /drive/v3/changes/watch
Subscribes to changes for a user. |


## REST Resource:
v3.channels


| Methods |  |
| --- | --- |
| stop | POST /drive/v3/channels/stop
Stops watching resources through this channel. |


## REST Resource:
v3.comments


| Methods |  |
| --- | --- |
| create | POST /drive/v3/files/{fileId}/comments
Creates a comment on a file. |
| delete | DELETE /drive/v3/files/{fileId}/comments/{commentId}
Deletes a comment. |
| get | GET /drive/v3/files/{fileId}/comments/{commentId}
Gets a comment by ID. |
| list | GET /drive/v3/files/{fileId}/comments
Lists a file's comments. |
| update | PATCH /drive/v3/files/{fileId}/comments/{commentId}
Updates a comment with patch semantics. |


## REST Resource:
v3.drives


| Methods |  |
| --- | --- |
| create | POST /drive/v3/drives
Creates a shared drive. |
| delete | DELETE /drive/v3/drives/{driveId}
Permanently deletes a shared drive for which the user is an
organizer
. |
| get | GET /drive/v3/drives/{driveId}
Gets a shared drive's metadata by ID. |
| hide | POST /drive/v3/drives/{driveId}/hide
Hides a shared drive from the default view. |
| list | GET /drive/v3/drives
Lists the user's shared drives. |
| unhide | POST /drive/v3/drives/{driveId}/unhide
Restores a shared drive to the default view. |
| update | PATCH /drive/v3/drives/{driveId}
Updates the metadata for a shared drive. |

Lists the user's shared drives.


## REST Resource:
v3.files


| Methods |  |
| --- | --- |
| copy | POST /drive/v3/files/{fileId}/copy
Creates a copy of a file and applies any requested updates with patch semantics. |
| create | POST /drive/v3/files
POST /upload/drive/v3/files
Creates a file. |
| delete | DELETE /drive/v3/files/{fileId}
Permanently deletes a file owned by the user without moving it to the trash. |
| download | POST /drive/v3/files/{fileId}/download
Downloads the content of a file. |
| emptyTrash | DELETE /drive/v3/files/trash
Permanently deletes all of the user's trashed files. |
| export | GET /drive/v3/files/{fileId}/export
Exports a Google Workspace document to the requested MIME type and returns exported byte content. |
| generateCseToken | GET /drive/v3/files/generateCseToken
Generates a CSE token which can be used to create or update CSE files. |
| generateIds | GET /drive/v3/files/generateIds
Generates a set of file IDs which can be provided in create or copy requests. |
| get | GET /drive/v3/files/{fileId}
Gets a file's metadata or content by ID. |
| list | GET /drive/v3/files
Lists the user's files. |
| listLabels | GET /drive/v3/files/{fileId}/listLabels
Lists the labels on a file. |
| modifyLabels | POST /drive/v3/files/{fileId}/modifyLabels
Modifies the set of labels applied to a file. |
| update | PATCH /drive/v3/files/{fileId}
PATCH /upload/drive/v3/files/{fileId}
Updates a file's metadata, content, or both. |
| watch | POST /drive/v3/files/{fileId}/watch
Subscribes to changes to a file. |

Creates a file.

Gets a file's metadata or content by ID.

Lists the user's files.

Updates a file's metadata, content, or both.


## REST Resource:
v3.operations


| Methods |  |
| --- | --- |
| get | GET /drive/v3/operations/{name}
Gets the latest state of a long-running operation. |


## REST Resource:
v3.permissions


| Methods |  |
| --- | --- |
| create | POST /drive/v3/files/{fileId}/permissions
Creates a permission for a file or shared drive. |
| delete | DELETE /drive/v3/files/{fileId}/permissions/{permissionId}
Deletes a permission. |
| get | GET /drive/v3/files/{fileId}/permissions/{permissionId}
Gets a permission by ID. |
| list | GET /drive/v3/files/{fileId}/permissions
Lists a file's or shared drive's permissions. |
| update | PATCH /drive/v3/files/{fileId}/permissions/{permissionId}
Updates a permission with patch semantics. |


## REST Resource:
v3.replies


| Methods |  |
| --- | --- |
| create | POST /drive/v3/files/{fileId}/comments/{commentId}/replies
Creates a reply to a comment. |
| delete | DELETE /drive/v3/files/{fileId}/comments/{commentId}/replies/{replyId}
Deletes a reply. |
| get | GET /drive/v3/files/{fileId}/comments/{commentId}/replies/{replyId}
Gets a reply by ID. |
| list | GET /drive/v3/files/{fileId}/comments/{commentId}/replies
Lists a comment's replies. |
| update | PATCH /drive/v3/files/{fileId}/comments/{commentId}/replies/{replyId}
Updates a reply with patch semantics. |


## REST Resource:
v3.revisions


| Methods |  |
| --- | --- |
| delete | DELETE /drive/v3/files/{fileId}/revisions/{revisionId}
Permanently deletes a file version. |
| get | GET /drive/v3/files/{fileId}/revisions/{revisionId}
Gets a revision's metadata or content by ID. |
| list | GET /drive/v3/files/{fileId}/revisions
Lists a file's revisions. |
| update | PATCH /drive/v3/files/{fileId}/revisions/{revisionId}
Updates a revision with patch semantics. |

Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2026-04-23 UTC.


---

# Label Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/reference/rest/v3/Label

- Home
- Google Workspace
- Google Drive
- Reference
- JSON representation
- Field
JSON representation
Representation of label and label fields.


| JSON representation |
| --- |
| {
"id"
:
string
,
"revisionId"
:
string
,
"kind"
:
string
,
"fields"
:
{
string
:
{
object (
Field
)
}
,
...
}
} |


```json
{
"id"
:
string
,
"revisionId"
:
string
,
"kind"
:
string
,
"fields"
:
{
string
:
{
object (
Field
)
}
,
...
}
}
```


| Fields |  |
| --- | --- |
| id | string
The ID of the label. |
| revisionId | string
The revision ID of the label. |
| kind | string
This is always drive#label |
| fields | map (key: string, value: object (
Field
))
A map of the fields on the label, keyed by the field's ID.
An object containing a list of
"key": value
pairs. Example:
{ "name": "wrench", "mass": "1.3kg", "count": "3" }
. |

string

The ID of the label.

The revision ID of the label.

This is always drive#label

map (key: string, value: object (
Field
))

A map of the fields on the label, keyed by the field's ID.

An object containing a list of
"key": value
pairs. Example:
{ "name": "wrench", "mass": "1.3kg", "count": "3" }
.


## Field

Representation of field, which is a typed key-value pair.


| JSON representation |
| --- |
| {
"kind"
:
string
,
"id"
:
string
,
"valueType"
:
string
,
"dateString"
:
[
string
]
,
"integer"
:
[
string
]
,
"selection"
:
[
string
]
,
"text"
:
[
string
]
,
"user"
:
[
{
object (
User
)
}
]
} |


```json
{
"kind"
:
string
,
"id"
:
string
,
"valueType"
:
string
,
"dateString"
:
[
string
]
,
"integer"
:
[
string
]
,
"selection"
:
[
string
]
,
"text"
:
[
string
]
,
"user"
:
[
{
object (
User
)
}
]
}
```


| Fields |  |
| --- | --- |
| kind | string
This is always drive#labelField. |
| id | string
The identifier of this label field. |
| valueType | string
The field type. While new values may be supported in the future, the following are currently allowed:
dateString
integer
selection
text
user |
| dateString[] | string
Only present if
valueType
is
dateString
. RFC 3339 formatted date: YYYY-MM-DD. |
| integer[] | string (
int64
format)
Only present if
valueType
is
integer
. |
| selection[] | string
Only present if
valueType
is
selection |
| text[] | string
Only present if
valueType
is
text
. |
| user[] | object (
User
)
Only present if
valueType
is
user
. |

This is always drive#labelField.

The identifier of this label field.

The field type. While new values may be supported in the future, the following are currently allowed:

- dateString
- integer
- selection
- text
- user
Only present if
valueType
is
dateString
. RFC 3339 formatted date: YYYY-MM-DD.

string (
int64
format)

Only present if
valueType
is
integer
.

Only present if
valueType
is
selection

Only present if
valueType
is
text
.

object (
User
)

Only present if
valueType
is
user
.

Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2026-04-21 UTC.


---

# User Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/reference/rest/v3/User

- Home
- Google Workspace
- Google Drive
- Reference
- JSON representation
Information about a Drive user.


| JSON representation |
| --- |
| {
"displayName"
:
string
,
"kind"
:
string
,
"me"
:
boolean
,
"permissionId"
:
string
,
"emailAddress"
:
string
,
"photoLink"
:
string
} |


```json
{
"displayName"
:
string
,
"kind"
:
string
,
"me"
:
boolean
,
"permissionId"
:
string
,
"emailAddress"
:
string
,
"photoLink"
:
string
}
```


| Fields |  |
| --- | --- |
| displayName | string
Output only. A plain text displayable name for this user. |
| kind | string
Output only. Identifies what kind of resource this is. Value: the fixed string
drive#user
. |
| me | boolean
Output only. Whether this user is the requesting user. |
| permissionId | string
Output only. The user's ID as visible in Permission resources. |
| emailAddress | string
Output only. The email address of the user. This may not be present in certain contexts if the user has not made their email address visible to the requester. |
| photoLink | string
Output only. A link to the user's profile photo, if available. |

string

Output only. A plain text displayable name for this user.

Output only. Identifies what kind of resource this is. Value: the fixed string
drive#user
.

boolean

Output only. Whether this user is the requesting user.

Output only. The user's ID as visible in Permission resources.

Output only. The email address of the user. This may not be present in certain contexts if the user has not made their email address visible to the requester.

Output only. A link to the user's profile photo, if available.

Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2025-07-23 UTC.


---

# REST Resource: about Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/reference/rest/v3/about

- Home
- Google Workspace
- Google Drive
- Reference
- Resource: About
JSON representation
- JSON representation
- Methods

## Resource: About

Information about the user, the user's Drive, and system capabilities.


| JSON representation |
| --- |
| {
"driveThemes"
:
[
{
"id"
:
string
,
"backgroundImageLink"
:
string
,
"colorRgb"
:
string
}
]
,
"importFormats"
:
{
string
:
value
,
...
}
,
"exportFormats"
:
{
string
:
value
,
...
}
,
"folderColorPalette"
:
[
string
]
,
"maxImportSizes"
:
{
string
:
string
,
...
}
,
"teamDriveThemes"
:
[
{
"id"
:
string
,
"backgroundImageLink"
:
string
,
"colorRgb"
:
string
}
]
,
"kind"
:
string
,
"storageQuota"
:
{
"limit"
:
string
,
"usageInDrive"
:
string
,
"usageInDriveTrash"
:
string
,
"usage"
:
string
}
,
"canCreateDrives"
:
boolean
,
"appInstalled"
:
boolean
,
"user"
:
{
object (
User
)
}
,
"maxUploadSize"
:
string
,
"canCreateTeamDrives"
:
boolean
} |


```json
{
"driveThemes"
:
[
{
"id"
:
string
,
"backgroundImageLink"
:
string
,
"colorRgb"
:
string
}
]
,
"importFormats"
:
{
string
:
value
,
...
}
,
"exportFormats"
:
{
string
:
value
,
...
}
,
"folderColorPalette"
:
[
string
]
,
"maxImportSizes"
:
{
string
:
string
,
...
}
,
"teamDriveThemes"
:
[
{
"id"
:
string
,
"backgroundImageLink"
:
string
,
"colorRgb"
:
string
}
]
,
"kind"
:
string
,
"storageQuota"
:
{
"limit"
:
string
,
"usageInDrive"
:
string
,
"usageInDriveTrash"
:
string
,
"usage"
:
string
}
,
"canCreateDrives"
:
boolean
,
"appInstalled"
:
boolean
,
"user"
:
{
object (
User
)
}
,
"maxUploadSize"
:
string
,
"canCreateTeamDrives"
:
boolean
}
```


| Fields |  |
| --- | --- |
| driveThemes[] | object
A list of themes that are supported for shared drives. |
| driveThemes[].id | string
The ID of the theme. |
| driveThemes[].backgroundImageLink | string
A link to this theme's background image. |
| driveThemes[].colorRgb | string
The color of this theme as an RGB hex string. |
| importFormats | map (key: string, value: value (
Value
format))
A map of source MIME type to possible targets for all supported imports.
An object containing a list of
"key": value
pairs. Example:
{ "name": "wrench", "mass": "1.3kg", "count": "3" }
. |
| exportFormats | map (key: string, value: value (
Value
format))
A map of source MIME type to possible targets for all supported exports.
An object containing a list of
"key": value
pairs. Example:
{ "name": "wrench", "mass": "1.3kg", "count": "3" }
. |
| folderColorPalette[] | string
The currently supported folder colors as RGB hex strings. |
| maxImportSizes | map (key: string, value: string (
int64
format))
A map of maximum import sizes by MIME type, in bytes.
An object containing a list of
"key": value
pairs. Example:
{ "name": "wrench", "mass": "1.3kg", "count": "3" }
. |
| teamDriveThemes[]
(deprecated) | object
Deprecated: Use
driveThemes
instead. |
| teamDriveThemes[]
(deprecated)
.id
(deprecated) | string
Deprecated: Use
driveThemes/id
instead. |
| teamDriveThemes[]
(deprecated)
.backgroundImageLink
(deprecated) | string
Deprecated: Use
driveThemes/backgroundImageLink
instead. |
| teamDriveThemes[]
(deprecated)
.colorRgb
(deprecated) | string
Deprecated: Use
driveThemes/colorRgb
instead. |
| kind | string
Identifies what kind of resource this is. Value: the fixed string
"drive#about"
. |
| storageQuota | object
The user's storage quota limits and usage. For users that are part of an organization with pooled storage, information about the limit and usage across all services is for the organization, rather than the individual user. All fields are measured in bytes. |
| storageQuota.limit | string (
int64
format)
The usage limit, if applicable. This will not be present if the user has unlimited storage. For users that are part of an organization with pooled storage, this is the limit for the organization, rather than the individual user. |
| storageQuota.usageInDrive | string (
int64
format)
The usage by all files in Google Drive. |
| storageQuota.usageInDriveTrash | string (
int64
format)
The usage by trashed files in Google Drive. |
| storageQuota.usage | string (
int64
format)
The total usage across all services. For users that are part of an organization with pooled storage, this is the usage across all services for the organization, rather than the individual user. |
| canCreateDrives | boolean
Whether the user can create shared drives. |
| appInstalled | boolean
Whether the user has installed the requesting app. |
| user | object (
User
)
The authenticated user. |
| maxUploadSize | string (
int64
format)
The maximum upload size in bytes. |
| canCreateTeamDrives
(deprecated) | boolean
Deprecated: Use
canCreateDrives
instead. |

object

A list of themes that are supported for shared drives.

string

The ID of the theme.

A link to this theme's background image.

The color of this theme as an RGB hex string.

map (key: string, value: value (
Value
format))

A map of source MIME type to possible targets for all supported imports.

An object containing a list of
"key": value
pairs. Example:
{ "name": "wrench", "mass": "1.3kg", "count": "3" }
.

A map of source MIME type to possible targets for all supported exports.

The currently supported folder colors as RGB hex strings.

map (key: string, value: string (
int64
format))

A map of maximum import sizes by MIME type, in bytes.

Deprecated: Use
driveThemes
instead.

Deprecated: Use
driveThemes/id
instead.

Deprecated: Use
driveThemes/backgroundImageLink
instead.

Deprecated: Use
driveThemes/colorRgb
instead.

Identifies what kind of resource this is. Value: the fixed string
"drive#about"
.

The user's storage quota limits and usage. For users that are part of an organization with pooled storage, information about the limit and usage across all services is for the organization, rather than the individual user. All fields are measured in bytes.

string (
int64
format)

The usage limit, if applicable. This will not be present if the user has unlimited storage. For users that are part of an organization with pooled storage, this is the limit for the organization, rather than the individual user.

The usage by all files in Google Drive.

The usage by trashed files in Google Drive.

The total usage across all services. For users that are part of an organization with pooled storage, this is the usage across all services for the organization, rather than the individual user.

boolean

Whether the user can create shared drives.

Whether the user has installed the requesting app.

object (
User
)

The authenticated user.

The maximum upload size in bytes.

Deprecated: Use
canCreateDrives
instead.


| Methods |  |
| --- | --- |
| get | Gets information about the user, the user's Drive, and system capabilities. |


## Methods


### get

Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2025-07-23 UTC.


---

# Method: about.get Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/reference/rest/v3/about/get

- Home
- Google Workspace
- Google Drive
- Reference
- HTTP request
- Request body
- Response body
- Authorization scopes
- Try it!
Gets information about the user, the user's Drive, and system capabilities. For more information, see
Return user info
.

Required: The
fields
parameter must be set. To return the exact fields you need, see
Return specific fields
.


### HTTP request

GET https://www.googleapis.com/drive/v3/about

The URL uses
gRPC Transcoding
syntax.


### Request body

The request body must be empty.


### Response body

If successful, the response body contains an instance of
About
.


### Authorization scopes

Requires one of the following OAuth scopes:

- https://www.googleapis.com/auth/drive
- https://www.googleapis.com/auth/drive.appdata
- https://www.googleapis.com/auth/drive.file
- https://www.googleapis.com/auth/drive.metadata
- https://www.googleapis.com/auth/drive.metadata.readonly
- https://www.googleapis.com/auth/drive.photos.readonly
- https://www.googleapis.com/auth/drive.readonly
Some scopes are restricted and require a security assessment for your app to use them. For more information, see the
Authorization guide
.

Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2025-04-18 UTC.


---

# REST Resource: accessproposals Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/reference/rest/v3/accessproposals

- Home
- Google Workspace
- Google Drive
- Reference
- Resource: AccessProposal
JSON representation
- JSON representation
- RoleAndView
JSON representation
- Methods

## Resource: AccessProposal

Manage outstanding access proposals on a file.


| JSON representation |
| --- |
| {
"fileId"
:
string
,
"proposalId"
:
string
,
"requesterEmailAddress"
:
string
,
"recipientEmailAddress"
:
string
,
"rolesAndViews"
:
[
{
object (
RoleAndView
)
}
]
,
"requestMessage"
:
string
,
"createTime"
:
string
} |


```json
{
"fileId"
:
string
,
"proposalId"
:
string
,
"requesterEmailAddress"
:
string
,
"recipientEmailAddress"
:
string
,
"rolesAndViews"
:
[
{
object (
RoleAndView
)
}
]
,
"requestMessage"
:
string
,
"createTime"
:
string
}
```


| Fields |  |
| --- | --- |
| fileId | string
The file ID that the proposal for access is on. |
| proposalId | string
The ID of the access proposal. |
| requesterEmailAddress | string
The email address of the requesting user. |
| recipientEmailAddress | string
The email address of the user that will receive permissions, if accepted. |
| rolesAndViews[] | object (
RoleAndView
)
A wrapper for the role and view of an access proposal. For more information, see
Roles and permissions
. |
| requestMessage | string
The message that the requester added to the proposal. |
| createTime | string (
Timestamp
format)
The creation time.
Uses RFC 3339, where generated output will always be Z-normalized and use 0, 3, 6 or 9 fractional digits. Offsets other than "Z" are also accepted. Examples:
"2014-10-02T15:01:23Z"
,
"2014-10-02T15:01:23.045123456Z"
or
"2014-10-02T15:01:23+05:30"
. |

string

The file ID that the proposal for access is on.

The ID of the access proposal.

The email address of the requesting user.

The email address of the user that will receive permissions, if accepted.

object (
RoleAndView
)

A wrapper for the role and view of an access proposal. For more information, see
Roles and permissions
.

The message that the requester added to the proposal.

string (
Timestamp
format)

The creation time.

Uses RFC 3339, where generated output will always be Z-normalized and use 0, 3, 6 or 9 fractional digits. Offsets other than "Z" are also accepted. Examples:
"2014-10-02T15:01:23Z"
,
"2014-10-02T15:01:23.045123456Z"
or
"2014-10-02T15:01:23+05:30"
.


## RoleAndView


| JSON representation |
| --- |
| {
"role"
:
string
,
"view"
:
string
} |


```json
{
"role"
:
string
,
"view"
:
string
}
```


| Fields |  |
| --- | --- |
| role | string
The role that was proposed by the requester. The supported values are:
writer
commenter
reader |
| view | string
Indicates the view for this access proposal. Only populated for proposals that belong to a view. Only
published
is supported. |

The role that was proposed by the requester. The supported values are:

- writer
- commenter
- reader
Indicates the view for this access proposal. Only populated for proposals that belong to a view. Only
published
is supported.


| Methods |  |
| --- | --- |
| get | Retrieves an access proposal by ID. |
| list | List the access proposals on a file. |
| resolve | Approves or denies an access proposal. |


## Methods


### get


### list


### resolve

Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2025-09-09 UTC.


---

# Method: accessproposals.get Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/reference/rest/v3/accessproposals/get

- Home
- Google Workspace
- Google Drive
- Reference
- HTTP request
- Path parameters
- Request body
- Response body
- Authorization scopes
- Try it!
Retrieves an access proposal by ID. For more information, see
Manage pending access proposals
.


### HTTP request

GET https://www.googleapis.com/drive/v3/files/{fileId}/accessproposals/{proposalId}

The URL uses
gRPC Transcoding
syntax.


### Path parameters


| Parameters |  |
| --- | --- |
| fileId | string
Required. The ID of the item the request is on. |
| proposalId | string
Required. The ID of the access proposal to resolve. |

string

Required. The ID of the item the request is on.

Required. The ID of the access proposal to resolve.


### Request body

The request body must be empty.


### Response body

If successful, the response body contains an instance of
AccessProposal
.


### Authorization scopes

Requires one of the following OAuth scopes:

- https://www.googleapis.com/auth/docs
- https://www.googleapis.com/auth/drive
- https://www.googleapis.com/auth/drive.file
- https://www.googleapis.com/auth/drive.metadata
- https://www.googleapis.com/auth/drive.metadata.readonly
- https://www.googleapis.com/auth/drive.readonly
Some scopes are restricted and require a security assessment for your app to use them. For more information, see the
Authorization guide
.

Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2025-09-09 UTC.


---

# Method: accessproposals.list Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/reference/rest/v3/accessproposals/list

- Home
- Google Workspace
- Google Drive
- Reference
- HTTP request
- Path parameters
- Query parameters
- Request body
- Response body
JSON representation
- JSON representation
- Authorization scopes
- Try it!
List the access proposals on a file. For more information, see
Manage pending access proposals
.

Note: Only approvers are able to list access proposals on a file. If the user isn't an approver, a 403 error is returned.


### HTTP request

GET https://www.googleapis.com/drive/v3/files/{fileId}/accessproposals

The URL uses
gRPC Transcoding
syntax.


### Path parameters


| Parameters |  |
| --- | --- |
| fileId | string
Required. The ID of the item the request is on. |

string

Required. The ID of the item the request is on.


### Query parameters


| Parameters |  |
| --- | --- |
| pageToken | string
Optional. The continuation token on the list of access requests. |
| pageSize | integer
Optional. The number of results per page. |

Optional. The continuation token on the list of access requests.

integer

Optional. The number of results per page.


### Request body

The request body must be empty.


### Response body

The response to an access proposal list request.

If successful, the response body contains data with the following structure:


| JSON representation |
| --- |
| {
"accessProposals"
:
[
{
object (
AccessProposal
)
}
]
,
"nextPageToken"
:
string
} |


```json
{
"accessProposals"
:
[
{
object (
AccessProposal
)
}
]
,
"nextPageToken"
:
string
}
```


| Fields |  |
| --- | --- |
| accessProposals[] | object (
AccessProposal
)
The list of access proposals. This field is only populated in Drive API v3. |
| nextPageToken | string
The continuation token for the next page of results. This will be absent if the end of the results list has been reached. If the token is rejected for any reason, it should be discarded, and pagination should be restarted from the first page of results. |

object (
AccessProposal
)

The list of access proposals. This field is only populated in Drive API v3.

The continuation token for the next page of results. This will be absent if the end of the results list has been reached. If the token is rejected for any reason, it should be discarded, and pagination should be restarted from the first page of results.


### Authorization scopes

Requires one of the following OAuth scopes:

- https://www.googleapis.com/auth/docs
- https://www.googleapis.com/auth/drive
- https://www.googleapis.com/auth/drive.file
- https://www.googleapis.com/auth/drive.metadata
- https://www.googleapis.com/auth/drive.metadata.readonly
- https://www.googleapis.com/auth/drive.readonly
Some scopes are restricted and require a security assessment for your app to use them. For more information, see the
Authorization guide
.

Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2025-09-09 UTC.


---

# Method: accessproposals.resolve Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/reference/rest/v3/accessproposals/resolve

- Home
- Google Workspace
- Google Drive
- Reference
- HTTP request
- Path parameters
- Request body
JSON representation
- JSON representation
- Response body
- Authorization scopes
- Action
- Try it!
Approves or denies an access proposal. For more information, see
Manage pending access proposals
.


### HTTP request

POST https://www.googleapis.com/drive/v3/files/{fileId}/accessproposals/{proposalId}:resolve

The URL uses
gRPC Transcoding
syntax.


### Path parameters


| Parameters |  |
| --- | --- |
| fileId | string
Required. The ID of the item the request is on. |
| proposalId | string
Required. The ID of the access proposal to resolve. |

string

Required. The ID of the item the request is on.

Required. The ID of the access proposal to resolve.


### Request body

The request body contains data with the following structure:


| JSON representation |
| --- |
| {
"role"
:
[
string
]
,
"view"
:
string
,
"action"
:
enum (
Action
)
,
"sendNotification"
:
boolean
} |


```json
{
"role"
:
[
string
]
,
"view"
:
string
,
"action"
:
enum (
Action
)
,
"sendNotification"
:
boolean
}
```


| Fields |  |
| --- | --- |
| role[] | string
Optional. The roles that the approver has allowed, if any. For more information, see
Roles and permissions
.
Note: This field is required for the
ACCEPT
action. |
| view | string
Optional. Indicates the view for this access proposal. This should only be set when the proposal belongs to a view. Only
published
is supported. |
| action | enum (
Action
)
Required. The action to take on the access proposal. |
| sendNotification | boolean
Optional. Whether to send an email to the requester when the access proposal is denied or accepted. |

Optional. The roles that the approver has allowed, if any. For more information, see
Roles and permissions
.

Note: This field is required for the
ACCEPT
action.

Optional. Indicates the view for this access proposal. This should only be set when the proposal belongs to a view. Only
published
is supported.

enum (
Action
)

Required. The action to take on the access proposal.

boolean

Optional. Whether to send an email to the requester when the access proposal is denied or accepted.


### Response body

If successful, the response body is an empty JSON object.


### Authorization scopes

Requires one of the following OAuth scopes:

- https://www.googleapis.com/auth/docs
- https://www.googleapis.com/auth/drive
- https://www.googleapis.com/auth/drive.file
Some scopes are restricted and require a security assessment for your app to use them. For more information, see the
Authorization guide
.


## Action

The state change of the access proposal.


| Enums |  |
| --- | --- |
| ACTION_UNSPECIFIED | Unspecified action |
| ACCEPT | The user accepts the access proposal.
Note: If this action is used, the
role
field must have at least one value. |
| DENY | The user denies the access proposal. |

The user accepts the access proposal.

Note: If this action is used, the
role
field must have at least one value.

Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2025-09-09 UTC.


---

# REST Resource: approvals Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/reference/rest/v3/approvals

- Home
- Google Workspace
- Google Drive
- Reference
- Resource: Approval
JSON representation
- JSON representation
- Status
- ReviewerResponse
JSON representation
- Response
- Methods

## Resource: Approval

Metadata for an approval. An approval is a review or approve process for a Drive item.


| JSON representation |
| --- |
| {
"kind"
:
string
,
"approvalId"
:
string
,
"targetFileId"
:
string
,
"createTime"
:
string
,
"modifyTime"
:
string
,
"completeTime"
:
string
,
"dueTime"
:
string
,
"status"
:
enum (
Status
)
,
"initiator"
:
{
object (
User
)
}
,
"reviewerResponses"
:
[
{
object (
ReviewerResponse
)
}
]
} |


```json
{
"kind"
:
string
,
"approvalId"
:
string
,
"targetFileId"
:
string
,
"createTime"
:
string
,
"modifyTime"
:
string
,
"completeTime"
:
string
,
"dueTime"
:
string
,
"status"
:
enum (
Status
)
,
"initiator"
:
{
object (
User
)
}
,
"reviewerResponses"
:
[
{
object (
ReviewerResponse
)
}
]
}
```


| Fields |  |
| --- | --- |
| kind | string
This is always drive#approval. |
| approvalId | string
The approval ID. |
| targetFileId | string
Target file id of the approval. |
| createTime | string (
Timestamp
format)
Output only. The time the approval was created.
Uses RFC 3339, where generated output will always be Z-normalized and use 0, 3, 6 or 9 fractional digits. Offsets other than "Z" are also accepted. Examples:
"2014-10-02T15:01:23Z"
,
"2014-10-02T15:01:23.045123456Z"
or
"2014-10-02T15:01:23+05:30"
. |
| modifyTime | string (
Timestamp
format)
Output only. The most recent time the approval was modified.
Uses RFC 3339, where generated output will always be Z-normalized and use 0, 3, 6 or 9 fractional digits. Offsets other than "Z" are also accepted. Examples:
"2014-10-02T15:01:23Z"
,
"2014-10-02T15:01:23.045123456Z"
or
"2014-10-02T15:01:23+05:30"
. |
| completeTime | string (
Timestamp
format)
Output only. The time the approval was completed.
Uses RFC 3339, where generated output will always be Z-normalized and use 0, 3, 6 or 9 fractional digits. Offsets other than "Z" are also accepted. Examples:
"2014-10-02T15:01:23Z"
,
"2014-10-02T15:01:23.045123456Z"
or
"2014-10-02T15:01:23+05:30"
. |
| dueTime | string (
Timestamp
format)
The time that the approval is due.
Uses RFC 3339, where generated output will always be Z-normalized and use 0, 3, 6 or 9 fractional digits. Offsets other than "Z" are also accepted. Examples:
"2014-10-02T15:01:23Z"
,
"2014-10-02T15:01:23.045123456Z"
or
"2014-10-02T15:01:23+05:30"
. |
| status | enum (
Status
)
Output only. The status of the approval at the time this resource was requested. |
| initiator | object (
User
)
The user that requested the approval. |
| reviewerResponses[] | object (
ReviewerResponse
)
The responses made on the approval by reviewers. |

string

This is always drive#approval.

The approval ID.

Target file id of the approval.

string (
Timestamp
format)

Output only. The time the approval was created.

Uses RFC 3339, where generated output will always be Z-normalized and use 0, 3, 6 or 9 fractional digits. Offsets other than "Z" are also accepted. Examples:
"2014-10-02T15:01:23Z"
,
"2014-10-02T15:01:23.045123456Z"
or
"2014-10-02T15:01:23+05:30"
.

Output only. The most recent time the approval was modified.

Output only. The time the approval was completed.

The time that the approval is due.

enum (
Status
)

Output only. The status of the approval at the time this resource was requested.

object (
User
)

The user that requested the approval.

object (
ReviewerResponse
)

The responses made on the approval by reviewers.


## Status

Possible statuses of an approval.


| Enums |  |
| --- | --- |
| STATUS_UNSPECIFIED | The approval status has not been set or was set to an invalid value. |
| IN_PROGRESS | The approval process has started and not finished. |
| APPROVED | The approval process is finished and the target was approved. |
| CANCELLED | The approval process was cancelled before it finished. |
| DECLINED | The approval process is finished and the target was declined. |


## ReviewerResponse

A response on an approval made by a specific reviewer.


| JSON representation |
| --- |
| {
"kind"
:
string
,
"reviewer"
:
{
object (
User
)
}
,
"response"
:
enum (
Response
)
} |


```json
{
"kind"
:
string
,
"reviewer"
:
{
object (
User
)
}
,
"response"
:
enum (
Response
)
}
```


| Fields |  |
| --- | --- |
| kind | string
This is always drive#reviewerResponse. |
| reviewer | object (
User
)
The user that's responsible for this response. |
| response | enum (
Response
)
A reviewer’s response for the approval. |

This is always drive#reviewerResponse.

The user that's responsible for this response.

enum (
Response
)

A reviewer’s response for the approval.


## Response

Possible responses for an approval.


| Enums |  |
| --- | --- |
| RESPONSE_UNSPECIFIED | The response was set to an unrecognized value. |
| NO_RESPONSE | The reviewer hasn't responded. |
| APPROVED | The reviewer has approved the item. |
| DECLINED | The reviewer has declined the item. |


| Methods |  |
| --- | --- |
| approve | Approves an approval. |
| cancel | Cancels an approval. |
| comment | Comments on an approval. |
| decline | Declines an approval. |
| get | Gets an approval by ID. |
| list | Lists the approvals on a file. |
| reassign | Reassigns the reviewers on an approval. |
| start | Starts an approval on a file. |


## Methods


### approve


### cancel


### comment


### decline


### get


### list


### reassign


### start

Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2026-04-23 UTC.


---

# Method: approvals.approve Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/reference/rest/v3/approvals/approve

- Home
- Google Workspace
- Google Drive
- Reference
- HTTP request
- Path parameters
- Request body
JSON representation
- JSON representation
- Response body
- Authorization scopes
- Try it!
Approves an approval. For more information, see
Manage approvals
.

This is used to update the
ReviewerResponse
of the requesting user with a
Response
of
APPROVED
. If this is the last required reviewer response, this also completes the approval and sets the approval
Status
to
APPROVED
.


### HTTP request

POST https://www.googleapis.com/drive/v3/files/{fileId}/approvals/{approvalId}:approve

The URL uses
gRPC Transcoding
syntax.


### Path parameters


| Parameters |  |
| --- | --- |
| fileId | string
Required. The ID of the file that the approval is on. |
| approvalId | string
Required. The ID of the approval to approve. |

string

Required. The ID of the file that the approval is on.

Required. The ID of the approval to approve.


### Request body

The request body contains data with the following structure:


| JSON representation |
| --- |
| {
"message"
:
string
} |


```json
{
"message"
:
string
}
```


| Fields |  |
| --- | --- |
| message | string
Optional. A message to accompany the reviewer response on the approval. This message is included in notifications for the action and in the approval activity log. |

Optional. A message to accompany the reviewer response on the approval. This message is included in notifications for the action and in the approval activity log.


### Response body

If successful, the response body contains an instance of
Approval
.


### Authorization scopes

Requires one of the following OAuth scopes:

- https://www.googleapis.com/auth/drive
- https://www.googleapis.com/auth/drive.file
- https://www.googleapis.com/auth/drive.metadata
Some scopes are restricted and require a security assessment for your app to use them. For more information, see the
Authorization guide
.

Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2026-04-23 UTC.


---

# Method: approvals.cancel Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/reference/rest/v3/approvals/cancel

- Home
- Google Workspace
- Google Drive
- Reference
- HTTP request
- Path parameters
- Request body
JSON representation
- JSON representation
- Response body
- Authorization scopes
- Try it!
Cancels an approval. For more information, see
Manage approvals
.

Updates the approval
Status
to
CANCELLED
. This can be called by any user with the
writer
permission on the file while the approval
Status
is
IN_PROGRESS
.


### HTTP request

POST https://www.googleapis.com/drive/v3/files/{fileId}/approvals/{approvalId}:cancel

The URL uses
gRPC Transcoding
syntax.


### Path parameters


| Parameters |  |
| --- | --- |
| fileId | string
Required. The ID of the file that the approval is on. |
| approvalId | string
Required. The ID of the approval to cancel. |

string

Required. The ID of the file that the approval is on.

Required. The ID of the approval to cancel.


### Request body

The request body contains data with the following structure:


| JSON representation |
| --- |
| {
"message"
:
string
} |


```json
{
"message"
:
string
}
```


| Fields |  |
| --- | --- |
| message | string
Optional. A message to accompany the cancellation of the approval. This message is included in notifications for the action and in the approval activity log. |

Optional. A message to accompany the cancellation of the approval. This message is included in notifications for the action and in the approval activity log.


### Response body

If successful, the response body contains an instance of
Approval
.


### Authorization scopes

Requires one of the following OAuth scopes:

- https://www.googleapis.com/auth/drive
- https://www.googleapis.com/auth/drive.file
- https://www.googleapis.com/auth/drive.metadata
Some scopes are restricted and require a security assessment for your app to use them. For more information, see the
Authorization guide
.

Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2026-04-23 UTC.


---

# Method: approvals.comment Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/reference/rest/v3/approvals/comment

- Home
- Google Workspace
- Google Drive
- Reference
- HTTP request
- Path parameters
- Request body
JSON representation
- JSON representation
- Response body
- Authorization scopes
- Try it!
Comments on an approval. For more information, see
Manage approvals
.

This sends a notification to both the initiator and the reviewers. Additionally, a message is also added to the approval activity log.


### HTTP request

POST https://www.googleapis.com/drive/v3/files/{fileId}/approvals/{approvalId}:comment

The URL uses
gRPC Transcoding
syntax.


### Path parameters


| Parameters |  |
| --- | --- |
| fileId | string
Required. The ID of the file that the approval is on. |
| approvalId | string
Required. The ID of the approval to comment on. |

string

Required. The ID of the file that the approval is on.

Required. The ID of the approval to comment on.


### Request body

The request body contains data with the following structure:


| JSON representation |
| --- |
| {
"message"
:
string
} |


```json
{
"message"
:
string
}
```


| Fields |  |
| --- | --- |
| message | string
Required. A message to comment on the approval. This message is included in notifications for the action and in the approval activity log. |

Required. A message to comment on the approval. This message is included in notifications for the action and in the approval activity log.


### Response body

If successful, the response body contains an instance of
Approval
.


### Authorization scopes

Requires one of the following OAuth scopes:

- https://www.googleapis.com/auth/drive
- https://www.googleapis.com/auth/drive.file
- https://www.googleapis.com/auth/drive.metadata
Some scopes are restricted and require a security assessment for your app to use them. For more information, see the
Authorization guide
.

Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2026-04-23 UTC.


---

# Method: approvals.decline Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/reference/rest/v3/approvals/decline

- Home
- Google Workspace
- Google Drive
- Reference
- HTTP request
- Path parameters
- Request body
JSON representation
- JSON representation
- Response body
- Authorization scopes
- Try it!
Declines an approval. For more information, see
Manage approvals
.

This is used to update the
ReviewerResponse
of the requesting user with a
Response
of
DECLINED
. This also completes the approval and sets the approval
Status
to
DECLINED
.


### HTTP request

POST https://www.googleapis.com/drive/v3/files/{fileId}/approvals/{approvalId}:decline

The URL uses
gRPC Transcoding
syntax.


### Path parameters


| Parameters |  |
| --- | --- |
| fileId | string
Required. The ID of the file that the approval is on. |
| approvalId | string
Required. The ID of the approval to decline. |

string

Required. The ID of the file that the approval is on.

Required. The ID of the approval to decline.


### Request body

The request body contains data with the following structure:


| JSON representation |
| --- |
| {
"message"
:
string
} |


```json
{
"message"
:
string
}
```


| Fields |  |
| --- | --- |
| message | string
Optional. A message to accompany the reviewer response on the approval. This message is included in notifications for the action and in the approval activity log. |

Optional. A message to accompany the reviewer response on the approval. This message is included in notifications for the action and in the approval activity log.


### Response body

If successful, the response body contains an instance of
Approval
.


### Authorization scopes

Requires one of the following OAuth scopes:

- https://www.googleapis.com/auth/drive
- https://www.googleapis.com/auth/drive.file
- https://www.googleapis.com/auth/drive.metadata
Some scopes are restricted and require a security assessment for your app to use them. For more information, see the
Authorization guide
.

Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2026-04-23 UTC.


---

# Method: approvals.get Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/reference/rest/v3/approvals/get

- Home
- Google Workspace
- Google Drive
- Reference
- HTTP request
- Path parameters
- Request body
- Response body
- Authorization scopes
- Try it!
Gets an approval by ID. For more information, see
Manage approvals
.


### HTTP request

GET https://www.googleapis.com/drive/v3/files/{fileId}/approvals/{approvalId}

The URL uses
gRPC Transcoding
syntax.


### Path parameters


| Parameters |  |
| --- | --- |
| fileId | string
Required. The ID of the file that the approval is on. |
| approvalId | string
Required. The ID of the approval. |

string

Required. The ID of the file that the approval is on.

Required. The ID of the approval.


### Request body

The request body must be empty.


### Response body

If successful, the response body contains an instance of
Approval
.


### Authorization scopes

Requires one of the following OAuth scopes:

- https://www.googleapis.com/auth/drive
- https://www.googleapis.com/auth/drive.appdata
- https://www.googleapis.com/auth/drive.file
- https://www.googleapis.com/auth/drive.metadata
- https://www.googleapis.com/auth/drive.metadata.readonly
- https://www.googleapis.com/auth/drive.readonly
Some scopes are restricted and require a security assessment for your app to use them. For more information, see the
Authorization guide
.

Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2026-04-23 UTC.


---

# Method: approvals.list Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/reference/rest/v3/approvals/list

- Home
- Google Workspace
- Google Drive
- Reference
- HTTP request
- Path parameters
- Query parameters
- Request body
- Response body
JSON representation
- JSON representation
- Authorization scopes
- Try it!
Lists the approvals on a file. For more information, see
Manage approvals
.


### HTTP request

GET https://www.googleapis.com/drive/v3/files/{fileId}/approvals

The URL uses
gRPC Transcoding
syntax.


### Path parameters


| Parameters |  |
| --- | --- |
| fileId | string
Required. The ID of the file that the approval is on. |

string

Required. The ID of the file that the approval is on.


### Query parameters


| Parameters |  |
| --- | --- |
| pageSize | integer
The maximum number of approvals to return. When not set, at most 100 approvals are returned. |
| pageToken | string
The token for continuing a previous list request on the next page. This should be set to the value of
nextPageToken
from a previous response. |

integer

The maximum number of approvals to return. When not set, at most 100 approvals are returned.

The token for continuing a previous list request on the next page. This should be set to the value of
nextPageToken
from a previous response.


### Request body

The request body must be empty.


### Response body

The response of an approvals list request.

If successful, the response body contains data with the following structure:


| JSON representation |
| --- |
| {
"kind"
:
string
,
"items"
:
[
{
object (
Approval
)
}
]
,
"nextPageToken"
:
string
} |


```json
{
"kind"
:
string
,
"items"
:
[
{
object (
Approval
)
}
]
,
"nextPageToken"
:
string
}
```


| Fields |  |
| --- | --- |
| kind | string
This is always drive#approvalList |
| items[] | object (
Approval
)
The list of approvals. If
nextPageToken
is populated, then this list may be incomplete and an additional page of results should be fetched. |
| nextPageToken | string
The page token for the next page of approvals. This is absent if the end of the approvals list has been reached. If the token is rejected for any reason, it should be discarded, and pagination should be restarted from the first page of results. |

This is always drive#approvalList

object (
Approval
)

The list of approvals. If
nextPageToken
is populated, then this list may be incomplete and an additional page of results should be fetched.

The page token for the next page of approvals. This is absent if the end of the approvals list has been reached. If the token is rejected for any reason, it should be discarded, and pagination should be restarted from the first page of results.


### Authorization scopes

Requires one of the following OAuth scopes:

- https://www.googleapis.com/auth/drive
- https://www.googleapis.com/auth/drive.appdata
- https://www.googleapis.com/auth/drive.file
- https://www.googleapis.com/auth/drive.metadata
- https://www.googleapis.com/auth/drive.metadata.readonly
- https://www.googleapis.com/auth/drive.readonly
Some scopes are restricted and require a security assessment for your app to use them. For more information, see the
Authorization guide
.

Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2026-04-23 UTC.


---

# Method: approvals.reassign Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/reference/rest/v3/approvals/reassign

- Home
- Google Workspace
- Google Drive
- Reference
- HTTP request
- Path parameters
- Request body
JSON representation
- JSON representation
- Response body
- Authorization scopes
- AddReviewer
JSON representation
- ReplaceReviewer
JSON representation
- Try it!
Reassigns the reviewers on an approval. For more information, see
Manage approvals
.

Adds or replaces reviewers in the
ReviewerResponse
of the approval.

This can be called by any user with the
writer
permission on the file while the approval
Status
is
IN_PROGRESS
and the
Response
for the reviewer being reassigned is
NO_RESPONSE
. A user with the
reader
permission can only reassign an approval that's assigned to themselves.

Removing a reviewer isn't allowed.


### HTTP request

POST https://www.googleapis.com/drive/v3/files/{fileId}/approvals/{approvalId}:reassign

The URL uses
gRPC Transcoding
syntax.


### Path parameters


| Parameters |  |
| --- | --- |
| fileId | string
Required. The ID of the file that the approval is on. |
| approvalId | string
Required. The ID of the approval to reassign. |

string

Required. The ID of the file that the approval is on.

Required. The ID of the approval to reassign.


### Request body

The request body contains data with the following structure:


| JSON representation |
| --- |
| {
"addReviewers"
:
[
{
object (
AddReviewer
)
}
]
,
"replaceReviewers"
:
[
{
object (
ReplaceReviewer
)
}
]
,
"message"
:
string
} |


```json
{
"addReviewers"
:
[
{
object (
AddReviewer
)
}
]
,
"replaceReviewers"
:
[
{
object (
ReplaceReviewer
)
}
]
,
"message"
:
string
}
```


| Fields |  |
| --- | --- |
| addReviewers[] | object (
AddReviewer
)
Optional. The list of reviewers to add. |
| replaceReviewers[] | object (
ReplaceReviewer
)
Optional. The list of reviewer replacements. |
| message | string
Optional. A message to send to the new reviewers. This message is included in notifications for the action and in the approval activity log. |

object (
AddReviewer
)

Optional. The list of reviewers to add.

object (
ReplaceReviewer
)

Optional. The list of reviewer replacements.

Optional. A message to send to the new reviewers. This message is included in notifications for the action and in the approval activity log.


### Response body

If successful, the response body contains an instance of
Approval
.


### Authorization scopes

Requires one of the following OAuth scopes:

- https://www.googleapis.com/auth/drive
- https://www.googleapis.com/auth/drive.file
- https://www.googleapis.com/auth/drive.metadata
Some scopes are restricted and require a security assessment for your app to use them. For more information, see the
Authorization guide
.


## AddReviewer

Representation of a reviewer addition.


| JSON representation |
| --- |
| {
"addedReviewerEmail"
:
string
} |


```json
{
"addedReviewerEmail"
:
string
}
```


| Fields |  |
| --- | --- |
| addedReviewerEmail | string
Required. The email of the reviewer to add. |

Required. The email of the reviewer to add.


## ReplaceReviewer

Representation of a reviewer replacement.


| JSON representation |
| --- |
| {
"addedReviewerEmail"
:
string
,
"removedReviewerEmail"
:
string
} |


```json
{
"addedReviewerEmail"
:
string
,
"removedReviewerEmail"
:
string
}
```


| Fields |  |
| --- | --- |
| addedReviewerEmail | string
Required. The email of the reviewer to add. |
| removedReviewerEmail | string
Required. The email of the reviewer to remove. |

Required. The email of the reviewer to remove.

Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2026-04-23 UTC.


---

# Method: approvals.start Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/reference/rest/v3/approvals/start

- Home
- Google Workspace
- Google Drive
- Reference
- HTTP request
- Path parameters
- Request body
JSON representation
- JSON representation
- Response body
- Authorization scopes
- Try it!
Starts an approval on a file. For more information, see
Manage approvals
.


### HTTP request

POST https://www.googleapis.com/drive/v3/files/{fileId}/approvals:start

The URL uses
gRPC Transcoding
syntax.


### Path parameters


| Parameters |  |
| --- | --- |
| fileId | string
Required. The ID of the file that the approval is created on. |

string

Required. The ID of the file that the approval is created on.


### Request body

The request body contains data with the following structure:


| JSON representation |
| --- |
| {
"reviewerEmails"
:
[
string
]
,
"dueTime"
:
string
,
"lockFile"
:
boolean
,
"message"
:
string
} |


```json
{
"reviewerEmails"
:
[
string
]
,
"dueTime"
:
string
,
"lockFile"
:
boolean
,
"message"
:
string
}
```


| Fields |  |
| --- | --- |
| reviewerEmails[] | string
Required. The emails of the users who are set to review the approval. |
| dueTime | string (
Timestamp
format)
Optional. The time that the approval is due.
Uses RFC 3339, where generated output will always be Z-normalized and use 0, 3, 6 or 9 fractional digits. Offsets other than "Z" are also accepted. Examples:
"2014-10-02T15:01:23Z"
,
"2014-10-02T15:01:23.045123456Z"
or
"2014-10-02T15:01:23+05:30"
. |
| lockFile | boolean
Optional. Whether to lock the file when starting the approval. |
| message | string
Optional. A message to send to reviewers when notifying them of the approval request. |

Required. The emails of the users who are set to review the approval.

string (
Timestamp
format)

Optional. The time that the approval is due.

Uses RFC 3339, where generated output will always be Z-normalized and use 0, 3, 6 or 9 fractional digits. Offsets other than "Z" are also accepted. Examples:
"2014-10-02T15:01:23Z"
,
"2014-10-02T15:01:23.045123456Z"
or
"2014-10-02T15:01:23+05:30"
.

boolean

Optional. Whether to lock the file when starting the approval.

Optional. A message to send to reviewers when notifying them of the approval request.


### Response body

If successful, the response body contains an instance of
Approval
.


### Authorization scopes

Requires one of the following OAuth scopes:

- https://www.googleapis.com/auth/drive
- https://www.googleapis.com/auth/drive.file
- https://www.googleapis.com/auth/drive.metadata
Some scopes are restricted and require a security assessment for your app to use them. For more information, see the
Authorization guide
.

Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2026-04-23 UTC.


---

# REST Resource: apps Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/reference/rest/v3/apps

- Home
- Google Workspace
- Google Drive
- Reference
- Resource: App
JSON representation
- JSON representation
- Icons
JSON representation
- Methods

## Resource: App

The
apps
resource provides a list of apps that a user has installed, with information about each app's supported MIME types, file extensions, and other details.

Some resource methods (such as
apps.get
) require an
appId
. Use the
apps.list
method to retrieve the ID for an installed application.


| JSON representation |
| --- |
| {
"primaryMimeTypes"
:
[
string
]
,
"secondaryMimeTypes"
:
[
string
]
,
"primaryFileExtensions"
:
[
string
]
,
"secondaryFileExtensions"
:
[
string
]
,
"icons"
:
[
{
object (
Icons
)
}
]
,
"name"
:
string
,
"objectType"
:
string
,
"supportsCreate"
:
boolean
,
"productUrl"
:
string
,
"id"
:
string
,
"supportsImport"
:
boolean
,
"installed"
:
boolean
,
"authorized"
:
boolean
,
"useByDefault"
:
boolean
,
"kind"
:
string
,
"shortDescription"
:
string
,
"longDescription"
:
string
,
"supportsMultiOpen"
:
boolean
,
"productId"
:
string
,
"openUrlTemplate"
:
string
,
"createUrl"
:
string
,
"createInFolderTemplate"
:
string
,
"supportsOfflineCreate"
:
boolean
,
"hasDriveWideScope"
:
boolean
} |


```json
{
"primaryMimeTypes"
:
[
string
]
,
"secondaryMimeTypes"
:
[
string
]
,
"primaryFileExtensions"
:
[
string
]
,
"secondaryFileExtensions"
:
[
string
]
,
"icons"
:
[
{
object (
Icons
)
}
]
,
"name"
:
string
,
"objectType"
:
string
,
"supportsCreate"
:
boolean
,
"productUrl"
:
string
,
"id"
:
string
,
"supportsImport"
:
boolean
,
"installed"
:
boolean
,
"authorized"
:
boolean
,
"useByDefault"
:
boolean
,
"kind"
:
string
,
"shortDescription"
:
string
,
"longDescription"
:
string
,
"supportsMultiOpen"
:
boolean
,
"productId"
:
string
,
"openUrlTemplate"
:
string
,
"createUrl"
:
string
,
"createInFolderTemplate"
:
string
,
"supportsOfflineCreate"
:
boolean
,
"hasDriveWideScope"
:
boolean
}
```


| Fields |  |
| --- | --- |
| primaryMimeTypes[] | string
The list of primary MIME types. |
| secondaryMimeTypes[] | string
The list of secondary MIME types. |
| primaryFileExtensions[] | string
The list of primary file extensions. |
| secondaryFileExtensions[] | string
The list of secondary file extensions. |
| icons[] | object (
Icons
)
The various icons for the app. |
| name | string
The name of the app. |
| objectType | string
The type of object this app creates such as a Chart. If empty, the app name should be used instead. |
| supportsCreate | boolean
Whether this app supports creating objects. |
| productUrl | string
A link to the product listing for this app. |
| id | string
The ID of the app. |
| supportsImport | boolean
Whether this app supports importing from Google Docs. |
| installed | boolean
Whether the app is installed. |
| authorized | boolean
Whether the app is authorized to access data on the user's Drive. |
| useByDefault | boolean
Whether the app is selected as the default handler for the types it supports. |
| kind | string
Output only. Identifies what kind of resource this is. Value: the fixed string "drive#app". |
| shortDescription | string
A short description of the app. |
| longDescription | string
A long description of the app. |
| supportsMultiOpen | boolean
Whether this app supports opening more than one file. |
| productId | string
The ID of the product listing for this app. |
| openUrlTemplate | string
The template URL for opening files with this app. The template contains
{ids}
or
{exportIds}
to be replaced by the actual file IDs. For more information, see
Open Files
for the full documentation. |
| createUrl | string
The URL to create a file with this app. |
| createInFolderTemplate | string
The template URL to create a file with this app in a given folder. The template contains the {folderId} to be replaced by the folder ID house the new file. |
| supportsOfflineCreate | boolean
Whether this app supports creating files when offline. |
| hasDriveWideScope | boolean
Whether the app has Drive-wide scope. An app with Drive-wide scope can access all files in the user's Drive. |

string

The list of primary MIME types.

The list of secondary MIME types.

The list of primary file extensions.

The list of secondary file extensions.

object (
Icons
)

The various icons for the app.

The name of the app.

The type of object this app creates such as a Chart. If empty, the app name should be used instead.

boolean

Whether this app supports creating objects.

A link to the product listing for this app.

The ID of the app.

Whether this app supports importing from Google Docs.

Whether the app is installed.

Whether the app is authorized to access data on the user's Drive.

Whether the app is selected as the default handler for the types it supports.

Output only. Identifies what kind of resource this is. Value: the fixed string "drive#app".

A short description of the app.

A long description of the app.

Whether this app supports opening more than one file.

The ID of the product listing for this app.

The template URL for opening files with this app. The template contains

{ids}

or

{exportIds}

to be replaced by the actual file IDs. For more information, see
Open Files
for the full documentation.

The URL to create a file with this app.

The template URL to create a file with this app in a given folder. The template contains the {folderId} to be replaced by the folder ID house the new file.

Whether this app supports creating files when offline.

Whether the app has Drive-wide scope. An app with Drive-wide scope can access all files in the user's Drive.


## Icons


| JSON representation |
| --- |
| {
"size"
:
integer
,
"category"
:
string
,
"iconUrl"
:
string
} |


```json
{
"size"
:
integer
,
"category"
:
string
,
"iconUrl"
:
string
}
```


| Fields |  |
| --- | --- |
| size | integer
Size of the icon. Represented as the maximum of the width and height. |
| category | string
Category of the icon. Allowed values are:
application
- The icon for the application.
document
- The icon for a file associated with the app.
documentShared
- The icon for a shared file associated with the app. |
| iconUrl | string
URL for the icon. |

integer

Size of the icon. Represented as the maximum of the width and height.

Category of the icon. Allowed values are:

- application
- The icon for the application.
- document
- The icon for a file associated with the app.
- documentShared
- The icon for a shared file associated with the app.
URL for the icon.


| Methods |  |
| --- | --- |
| get | Gets a specific app. |
| list | Lists a user's installed apps. |


## Methods


### get


### list

Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2025-07-23 UTC.


---

# Method: apps.get Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/reference/rest/v3/apps/get

- Home
- Google Workspace
- Google Drive
- Reference
- HTTP request
- Path parameters
- Request body
- Response body
- Authorization scopes
- Try it!
Gets a specific app. For more information, see
Return user info
.


### HTTP request

GET https://www.googleapis.com/drive/v3/apps/{appId}

The URL uses
gRPC Transcoding
syntax.


### Path parameters


| Parameters |  |
| --- | --- |
| appId | string
The ID of the app. |

string

The ID of the app.


### Request body

The request body must be empty.


### Response body

If successful, the response body contains an instance of
App
.


### Authorization scopes

Requires one of the following OAuth scopes:

- https://www.googleapis.com/auth/docs
- https://www.googleapis.com/auth/drive
- https://www.googleapis.com/auth/drive.appdata
- https://www.googleapis.com/auth/drive.apps.readonly
- https://www.googleapis.com/auth/drive.file
- https://www.googleapis.com/auth/drive.metadata
- https://www.googleapis.com/auth/drive.metadata.readonly
- https://www.googleapis.com/auth/drive.readonly
Some scopes are restricted and require a security assessment for your app to use them. For more information, see the
Authorization guide
.

Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2025-04-18 UTC.


---

# Method: apps.list Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/reference/rest/v3/apps/list

- Home
- Google Workspace
- Google Drive
- Reference
- HTTP request
- Query parameters
- Request body
- Response body
JSON representation
- JSON representation
- Authorization scopes
- Try it!
Lists a user's installed apps. For more information, see
Return user info
.


### HTTP request

GET https://www.googleapis.com/drive/v3/apps

The URL uses
gRPC Transcoding
syntax.


### Query parameters


| Parameters |  |
| --- | --- |
| appFilterExtensions | string
A comma-separated list of file extensions to limit returned results. All results within the given app query scope which can open any of the given file extensions are included in the response. If
appFilterMimeTypes
are provided as well, the result is a union of the two resulting app lists. |
| appFilterMimeTypes | string
A comma-separated list of file extensions to limit returned results. All results within the given app query scope which can open any of the given MIME types will be included in the response. If
appFilterExtensions
are provided as well, the result is a union of the two resulting app lists. |
| languageCode | string
A language or locale code, as defined by BCP 47, with some extensions from Unicode's LDML format (
http://www.unicode.org/reports/tr35/)
. |

string

A comma-separated list of file extensions to limit returned results. All results within the given app query scope which can open any of the given file extensions are included in the response. If
appFilterMimeTypes
are provided as well, the result is a union of the two resulting app lists.

A comma-separated list of file extensions to limit returned results. All results within the given app query scope which can open any of the given MIME types will be included in the response. If
appFilterExtensions
are provided as well, the result is a union of the two resulting app lists.

A language or locale code, as defined by BCP 47, with some extensions from Unicode's LDML format (
http://www.unicode.org/reports/tr35/)
.


### Request body

The request body must be empty.


### Response body

A list of third-party applications which the user has installed or given access to Google Drive.

If successful, the response body contains data with the following structure:


| JSON representation |
| --- |
| {
"defaultAppIds"
:
[
string
]
,
"items"
:
[
{
object (
App
)
}
]
,
"kind"
:
string
,
"selfLink"
:
string
} |


```json
{
"defaultAppIds"
:
[
string
]
,
"items"
:
[
{
object (
App
)
}
]
,
"kind"
:
string
,
"selfLink"
:
string
}
```


| Fields |  |
| --- | --- |
| defaultAppIds[] | string
The list of app IDs that the user has specified to use by default. The list is in reverse-priority order (lowest to highest). |
| items[] | object (
App
)
The list of apps. |
| kind | string
Output only. Identifies what kind of resource this is. Value: the fixed string "drive#appList". |
| selfLink | string
A link back to this list. |

The list of app IDs that the user has specified to use by default. The list is in reverse-priority order (lowest to highest).

object (
App
)

The list of apps.

Output only. Identifies what kind of resource this is. Value: the fixed string "drive#appList".

A link back to this list.


### Authorization scopes

Requires the following OAuth scope:

- https://www.googleapis.com/auth/drive.apps.readonly
Some scopes are restricted and require a security assessment for your app to use them. For more information, see the
Authorization guide
.

Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2025-07-23 UTC.


---

# REST Resource: changes Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/reference/rest/v3/changes

- Home
- Google Workspace
- Google Drive
- Reference
- Resource: Change
JSON representation
- JSON representation
- Methods

## Resource: Change

A change to a file or shared drive.


| JSON representation |
| --- |
| {
"kind"
:
string
,
"removed"
:
boolean
,
"file"
:
{
object (
File
)
}
,
"fileId"
:
string
,
"time"
:
string
,
"driveId"
:
string
,
"type"
:
string
,
"teamDriveId"
:
string
,
"teamDrive"
:
{
object (
TeamDrive
)
}
,
"changeType"
:
string
,
"drive"
:
{
object (
Drive
)
}
} |


```json
{
"kind"
:
string
,
"removed"
:
boolean
,
"file"
:
{
object (
File
)
}
,
"fileId"
:
string
,
"time"
:
string
,
"driveId"
:
string
,
"type"
:
string
,
"teamDriveId"
:
string
,
"teamDrive"
:
{
object (
TeamDrive
)
}
,
"changeType"
:
string
,
"drive"
:
{
object (
Drive
)
}
}
```


| Fields |  |
| --- | --- |
| kind | string
Identifies what kind of resource this is. Value: the fixed string
"drive#change"
. |
| removed | boolean
Whether the file or shared drive has been removed from this list of changes, for example by deletion or loss of access. |
| file | object (
File
)
The updated state of the file. Present if the type is file and the file has not been removed from this list of changes. |
| fileId | string
The ID of the file which has changed. |
| time | string
The time of this change (RFC 3339 date-time). |
| driveId | string
The ID of the shared drive associated with this change. |
| type
(deprecated) | string
Deprecated: Use
changeType
instead. |
| teamDriveId
(deprecated) | string
Deprecated: Use
driveId
instead. |
| teamDrive
(deprecated) | object (
TeamDrive
)
Deprecated: Use
drive
instead. |
| changeType | string
The type of the change. Possible values are
file
and
drive
. |
| drive | object (
Drive
)
The updated state of the shared drive. Present if the changeType is drive, the user is still a member of the shared drive, and the shared drive has not been deleted. |

string

Identifies what kind of resource this is. Value: the fixed string
"drive#change"
.

boolean

Whether the file or shared drive has been removed from this list of changes, for example by deletion or loss of access.

object (
File
)

The updated state of the file. Present if the type is file and the file has not been removed from this list of changes.

The ID of the file which has changed.

The time of this change (RFC 3339 date-time).

The ID of the shared drive associated with this change.

Deprecated: Use
changeType
instead.

Deprecated: Use
driveId
instead.

object (
TeamDrive
)

Deprecated: Use
drive
instead.

The type of the change. Possible values are
file
and
drive
.

object (
Drive
)

The updated state of the shared drive. Present if the changeType is drive, the user is still a member of the shared drive, and the shared drive has not been deleted.


| Methods |  |
| --- | --- |
| getStartPageToken | Gets the starting pageToken for listing future changes. |
| list | Lists the changes for a user or shared drive. |
| watch | Subscribes to changes for a user. |


## Methods


### getStartPageToken


### list


### watch

Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2025-04-18 UTC.


---

# Method: changes.getStartPageToken Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/reference/rest/v3/changes/getStartPageToken

- Home
- Google Workspace
- Google Drive
- Reference
- HTTP request
- Query parameters
- Request body
- Response body
JSON representation
- JSON representation
- Authorization scopes
- Try it!
Gets the starting pageToken for listing future changes. For more information, see
Retrieve changes
.


### HTTP request

GET https://www.googleapis.com/drive/v3/changes/startPageToken

The URL uses
gRPC Transcoding
syntax.


### Query parameters


| Parameters |  |
| --- | --- |
| driveId | string
The ID of the shared drive for which the starting pageToken for listing future changes from that shared drive will be returned. |
| supportsAllDrives | boolean
Whether the requesting application supports both My Drives and shared drives. |
| supportsTeamDrives
(deprecated) | boolean
Deprecated: Use
supportsAllDrives
instead. |
| teamDriveId
(deprecated) | string
Deprecated: Use
driveId
instead. |

string

The ID of the shared drive for which the starting pageToken for listing future changes from that shared drive will be returned.

boolean

Whether the requesting application supports both My Drives and shared drives.

Deprecated: Use
supportsAllDrives
instead.

Deprecated: Use
driveId
instead.


### Request body

The request body must be empty.


### Response body

If successful, the response body contains data with the following structure:


| JSON representation |
| --- |
| {
"startPageToken"
:
string
,
"kind"
:
string
} |


```json
{
"startPageToken"
:
string
,
"kind"
:
string
}
```


| Fields |  |
| --- | --- |
| startPageToken | string
The starting page token for listing future changes. The page token doesn't expire. |
| kind | string
Identifies what kind of resource this is. Value: the fixed string
"drive#startPageToken"
. |

The starting page token for listing future changes. The page token doesn't expire.

Identifies what kind of resource this is. Value: the fixed string
"drive#startPageToken"
.


### Authorization scopes

Requires one of the following OAuth scopes:

- https://www.googleapis.com/auth/drive
- https://www.googleapis.com/auth/drive.appdata
- https://www.googleapis.com/auth/drive.file
- https://www.googleapis.com/auth/drive.meet.readonly
- https://www.googleapis.com/auth/drive.metadata
- https://www.googleapis.com/auth/drive.metadata.readonly
- https://www.googleapis.com/auth/drive.photos.readonly
- https://www.googleapis.com/auth/drive.readonly
Some scopes are restricted and require a security assessment for your app to use them. For more information, see the
Authorization guide
.

Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2025-04-18 UTC.


---

# Method: changes.list Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/reference/rest/v3/changes/list

- Home
- Google Workspace
- Google Drive
- Reference
- HTTP request
- Query parameters
- Request body
- Response body
JSON representation
- JSON representation
- Authorization scopes
- Try it!
Lists the changes for a user or shared drive. For more information, see
Retrieve changes
.


### HTTP request

GET https://www.googleapis.com/drive/v3/changes

The URL uses
gRPC Transcoding
syntax.


### Query parameters


| Parameters |  |
| --- | --- |
| driveId | string
The shared drive from which changes will be returned. If specified the change IDs will be reflective of the shared drive; use the combined drive ID and change ID as an identifier. |
| includeCorpusRemovals | boolean
Whether changes should include the file resource if the file is still accessible by the user at the time of the request, even when a file was removed from the list of changes and there will be no further change entries for this file. |
| includeItemsFromAllDrives | boolean
Whether both My Drive and shared drive items should be included in results. |
| includeRemoved | boolean
Whether to include changes indicating that items have been removed from the list of changes, for example by deletion or loss of access. |
| includeTeamDriveItems
(deprecated) | boolean
Deprecated: Use
includeItemsFromAllDrives
instead. |
| pageSize | integer
The maximum number of changes to return per page. |
| pageToken | string
The token for continuing a previous list request on the next page. This should be set to the value of 'nextPageToken' from the previous response or to the response from the getStartPageToken method. |
| restrictToMyDrive | boolean
Whether to restrict the results to changes inside the My Drive hierarchy. This omits changes to files such as those in the Application Data folder or shared files which have not been added to My Drive. |
| spaces | string
A comma-separated list of spaces to query within the corpora. Supported values are 'drive' and 'appDataFolder'. |
| supportsAllDrives | boolean
Whether the requesting application supports both My Drives and shared drives. |
| supportsTeamDrives
(deprecated) | boolean
Deprecated: Use
supportsAllDrives
instead. |
| teamDriveId
(deprecated) | string
Deprecated: Use
driveId
instead. |
| includePermissionsForView | string
Specifies which additional view's permissions to include in the response. Only 'published' is supported. |
| includeLabels | string
A comma-separated list of IDs of labels to include in the
labelInfo
part of the response. |

string

The shared drive from which changes will be returned. If specified the change IDs will be reflective of the shared drive; use the combined drive ID and change ID as an identifier.

boolean

Whether changes should include the file resource if the file is still accessible by the user at the time of the request, even when a file was removed from the list of changes and there will be no further change entries for this file.

Whether both My Drive and shared drive items should be included in results.

Whether to include changes indicating that items have been removed from the list of changes, for example by deletion or loss of access.

Deprecated: Use
includeItemsFromAllDrives
instead.

integer

The maximum number of changes to return per page.

The token for continuing a previous list request on the next page. This should be set to the value of 'nextPageToken' from the previous response or to the response from the getStartPageToken method.

Whether to restrict the results to changes inside the My Drive hierarchy. This omits changes to files such as those in the Application Data folder or shared files which have not been added to My Drive.

A comma-separated list of spaces to query within the corpora. Supported values are 'drive' and 'appDataFolder'.

Whether the requesting application supports both My Drives and shared drives.

Deprecated: Use
supportsAllDrives
instead.

Deprecated: Use
driveId
instead.

Specifies which additional view's permissions to include in the response. Only 'published' is supported.

A comma-separated list of IDs of labels to include in the
labelInfo
part of the response.


### Request body

The request body must be empty.


### Response body

A list of changes for a user.

If successful, the response body contains data with the following structure:


| JSON representation |
| --- |
| {
"changes"
:
[
{
object (
Change
)
}
]
,
"kind"
:
string
,
"nextPageToken"
:
string
,
"newStartPageToken"
:
string
} |


```json
{
"changes"
:
[
{
object (
Change
)
}
]
,
"kind"
:
string
,
"nextPageToken"
:
string
,
"newStartPageToken"
:
string
}
```


| Fields |  |
| --- | --- |
| changes[] | object (
Change
)
The list of changes. If nextPageToken is populated, then this list may be incomplete and an additional page of results should be fetched. |
| kind | string
Identifies what kind of resource this is. Value: the fixed string
"drive#changeList"
. |
| nextPageToken | string
The page token for the next page of changes. This will be absent if the end of the changes list has been reached. The page token doesn't expire. |
| newStartPageToken | string
The starting page token for future changes. This will be present only if the end of the current changes list has been reached. The page token doesn't expire. |

object (
Change
)

The list of changes. If nextPageToken is populated, then this list may be incomplete and an additional page of results should be fetched.

Identifies what kind of resource this is. Value: the fixed string
"drive#changeList"
.

The page token for the next page of changes. This will be absent if the end of the changes list has been reached. The page token doesn't expire.

The starting page token for future changes. This will be present only if the end of the current changes list has been reached. The page token doesn't expire.


### Authorization scopes

Requires one of the following OAuth scopes:

- https://www.googleapis.com/auth/drive
- https://www.googleapis.com/auth/drive.appdata
- https://www.googleapis.com/auth/drive.file
- https://www.googleapis.com/auth/drive.meet.readonly
- https://www.googleapis.com/auth/drive.metadata
- https://www.googleapis.com/auth/drive.metadata.readonly
- https://www.googleapis.com/auth/drive.photos.readonly
- https://www.googleapis.com/auth/drive.readonly
Some scopes are restricted and require a security assessment for your app to use them. For more information, see the
Authorization guide
.

Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2025-07-23 UTC.


---

# Method: changes.watch Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/reference/rest/v3/changes/watch

- Home
- Google Workspace
- Google Drive
- Reference
- HTTP request
- Query parameters
- Request body
- Response body
- Authorization scopes
Subscribes to changes for a user. For more information, see
Notifications for resource changes
.


### HTTP request

POST https://www.googleapis.com/drive/v3/changes/watch

The URL uses
gRPC Transcoding
syntax.


### Query parameters


| Parameters |  |
| --- | --- |
| driveId | string
The shared drive from which changes will be returned. If specified the change IDs will be reflective of the shared drive; use the combined drive ID and change ID as an identifier. |
| includeCorpusRemovals | boolean
Whether changes should include the file resource if the file is still accessible by the user at the time of the request, even when a file was removed from the list of changes and there will be no further change entries for this file. |
| includeItemsFromAllDrives | boolean
Whether both My Drive and shared drive items should be included in results. |
| includeRemoved | boolean
Whether to include changes indicating that items have been removed from the list of changes, for example by deletion or loss of access. |
| includeTeamDriveItems
(deprecated) | boolean
Deprecated: Use
includeItemsFromAllDrives
instead. |
| pageSize | integer
The maximum number of changes to return per page. |
| pageToken | string
The token for continuing a previous list request on the next page. This should be set to the value of 'nextPageToken' from the previous response or to the response from the getStartPageToken method. |
| restrictToMyDrive | boolean
Whether to restrict the results to changes inside the My Drive hierarchy. This omits changes to files such as those in the Application Data folder or shared files which have not been added to My Drive. |
| spaces | string
A comma-separated list of spaces to query within the corpora. Supported values are 'drive' and 'appDataFolder'. |
| supportsAllDrives | boolean
Whether the requesting application supports both My Drives and shared drives. |
| supportsTeamDrives
(deprecated) | boolean
Deprecated: Use
supportsAllDrives
instead. |
| teamDriveId
(deprecated) | string
Deprecated: Use
driveId
instead. |
| includePermissionsForView | string
Specifies which additional view's permissions to include in the response. Only 'published' is supported. |
| includeLabels | string
A comma-separated list of IDs of labels to include in the
labelInfo
part of the response. |

string

The shared drive from which changes will be returned. If specified the change IDs will be reflective of the shared drive; use the combined drive ID and change ID as an identifier.

boolean

Whether changes should include the file resource if the file is still accessible by the user at the time of the request, even when a file was removed from the list of changes and there will be no further change entries for this file.

Whether both My Drive and shared drive items should be included in results.

Whether to include changes indicating that items have been removed from the list of changes, for example by deletion or loss of access.

Deprecated: Use
includeItemsFromAllDrives
instead.

integer

The maximum number of changes to return per page.

The token for continuing a previous list request on the next page. This should be set to the value of 'nextPageToken' from the previous response or to the response from the getStartPageToken method.

Whether to restrict the results to changes inside the My Drive hierarchy. This omits changes to files such as those in the Application Data folder or shared files which have not been added to My Drive.

A comma-separated list of spaces to query within the corpora. Supported values are 'drive' and 'appDataFolder'.

Whether the requesting application supports both My Drives and shared drives.

Deprecated: Use
supportsAllDrives
instead.

Deprecated: Use
driveId
instead.

Specifies which additional view's permissions to include in the response. Only 'published' is supported.

A comma-separated list of IDs of labels to include in the
labelInfo
part of the response.


### Request body

The request body contains an instance of
Channel
.


### Response body

If successful, the response body contains an instance of
Channel
.


### Authorization scopes

Requires one of the following OAuth scopes:

- https://www.googleapis.com/auth/drive
- https://www.googleapis.com/auth/drive.appdata
- https://www.googleapis.com/auth/drive.file
- https://www.googleapis.com/auth/drive.meet.readonly
- https://www.googleapis.com/auth/drive.metadata
- https://www.googleapis.com/auth/drive.metadata.readonly
- https://www.googleapis.com/auth/drive.photos.readonly
- https://www.googleapis.com/auth/drive.readonly
Some scopes are restricted and require a security assessment for your app to use them. For more information, see the
Authorization guide
.

Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2025-04-18 UTC.


---

# REST Resource: channels Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/reference/rest/v3/channels

- Home
- Google Workspace
- Google Drive
- Reference
- Resource: Channel
JSON representation
- JSON representation
- Methods

## Resource: Channel

A notification channel used to watch for resource changes.


| JSON representation |
| --- |
| {
"params"
:
{
string
:
string
,
...
}
,
"payload"
:
boolean
,
"id"
:
string
,
"resourceId"
:
string
,
"resourceUri"
:
string
,
"token"
:
string
,
"expiration"
:
string
,
"type"
:
string
,
"address"
:
string
,
"kind"
:
string
} |


```json
{
"params"
:
{
string
:
string
,
...
}
,
"payload"
:
boolean
,
"id"
:
string
,
"resourceId"
:
string
,
"resourceUri"
:
string
,
"token"
:
string
,
"expiration"
:
string
,
"type"
:
string
,
"address"
:
string
,
"kind"
:
string
}
```


| Fields |  |
| --- | --- |
| params | map (key: string, value: string)
Additional parameters controlling delivery channel behavior. Optional.
An object containing a list of
"key": value
pairs. Example:
{ "name": "wrench", "mass": "1.3kg", "count": "3" }
. |
| payload | boolean
A Boolean value to indicate whether payload is wanted. Optional. |
| id | string
A UUID or similar unique string that identifies this channel. |
| resourceId | string
An opaque ID that identifies the resource being watched on this channel. Stable across different API versions. |
| resourceUri | string
A version-specific identifier for the watched resource. |
| token | string
An arbitrary string delivered to the target address with each notification delivered over this channel. Optional. |
| expiration | string (
int64
format)
Date and time of notification channel expiration, expressed as a Unix timestamp, in milliseconds. Optional. |
| type | string
The type of delivery mechanism used for this channel. Valid values are "web_hook" or "webhook". |
| address | string
The address where notifications are delivered for this channel. |
| kind | string
Identifies this as a notification channel used to watch for changes to a resource, which is
api#channel
. |

map (key: string, value: string)

Additional parameters controlling delivery channel behavior. Optional.

An object containing a list of
"key": value
pairs. Example:
{ "name": "wrench", "mass": "1.3kg", "count": "3" }
.

boolean

A Boolean value to indicate whether payload is wanted. Optional.

string

A UUID or similar unique string that identifies this channel.

An opaque ID that identifies the resource being watched on this channel. Stable across different API versions.

A version-specific identifier for the watched resource.

An arbitrary string delivered to the target address with each notification delivered over this channel. Optional.

string (
int64
format)

Date and time of notification channel expiration, expressed as a Unix timestamp, in milliseconds. Optional.

The type of delivery mechanism used for this channel. Valid values are "web_hook" or "webhook".

The address where notifications are delivered for this channel.

Identifies this as a notification channel used to watch for changes to a resource, which is
api#channel
.


| Methods |  |
| --- | --- |
| stop | Stops watching resources through this channel. |


## Methods


### stop

Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2025-07-23 UTC.


---

# Method: channels.stop Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/reference/rest/v3/channels/stop

- Home
- Google Workspace
- Google Drive
- Reference
- HTTP request
- Request body
- Response body
- Authorization scopes
Stops watching resources through this channel. For more information, see
Notifications for resource changes
.


### HTTP request

POST https://www.googleapis.com/drive/v3/channels/stop

The URL uses
gRPC Transcoding
syntax.


### Request body

The request body contains an instance of
Channel
.


### Response body

If successful, the response body is an empty JSON object.


### Authorization scopes

Requires one of the following OAuth scopes:

- https://www.googleapis.com/auth/docs
- https://www.googleapis.com/auth/drive
- https://www.googleapis.com/auth/drive.appdata
- https://www.googleapis.com/auth/drive.apps
- https://www.googleapis.com/auth/drive.file
- https://www.googleapis.com/auth/drive.meet.readonly
- https://www.googleapis.com/auth/drive.metadata
- https://www.googleapis.com/auth/drive.metadata.readonly
- https://www.googleapis.com/auth/drive.photos.readonly
- https://www.googleapis.com/auth/drive.readonly
Some scopes are restricted and require a security assessment for your app to use them. For more information, see the
Authorization guide
.

Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2025-04-18 UTC.


---

# REST Resource: comments Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/reference/rest/v3/comments

- Home
- Google Workspace
- Google Drive
- Reference
- Resource: Comment
JSON representation
- JSON representation
- Methods

## Resource: Comment

A comment on a file.

Some resource methods (such as
comments.update
) require a
commentId
. Use the
comments.list
method to retrieve the ID for a comment in a file.


| JSON representation |
| --- |
| {
"replies"
:
[
{
object (
Reply
)
}
]
,
"mentionedEmailAddresses"
:
[
string
]
,
"id"
:
string
,
"kind"
:
string
,
"createdTime"
:
string
,
"modifiedTime"
:
string
,
"resolved"
:
boolean
,
"anchor"
:
string
,
"author"
:
{
object (
User
)
}
,
"deleted"
:
boolean
,
"htmlContent"
:
string
,
"content"
:
string
,
"quotedFileContent"
:
{
"mimeType"
:
string
,
"value"
:
string
}
,
"assigneeEmailAddress"
:
string
} |


```json
{
"replies"
:
[
{
object (
Reply
)
}
]
,
"mentionedEmailAddresses"
:
[
string
]
,
"id"
:
string
,
"kind"
:
string
,
"createdTime"
:
string
,
"modifiedTime"
:
string
,
"resolved"
:
boolean
,
"anchor"
:
string
,
"author"
:
{
object (
User
)
}
,
"deleted"
:
boolean
,
"htmlContent"
:
string
,
"content"
:
string
,
"quotedFileContent"
:
{
"mimeType"
:
string
,
"value"
:
string
}
,
"assigneeEmailAddress"
:
string
}
```


| Fields |  |
| --- | --- |
| replies[] | object (
Reply
)
Output only. The full list of replies to the comment in chronological order. |
| mentionedEmailAddresses[] | string
Output only. A list of email addresses for users mentioned in this comment. If no users are mentioned, the list is empty. |
| id | string
Output only. The ID of the comment. |
| kind | string
Output only. Identifies what kind of resource this is. Value: the fixed string
"drive#comment"
. |
| createdTime | string
Output only. The time at which the comment was created (RFC 3339 date-time). |
| modifiedTime | string
Output only. The last time the comment or any of its replies was modified (RFC 3339 date-time). |
| resolved | boolean
Output only. Whether the comment has been resolved by one of its replies. |
| anchor | string
A region of the document represented as a JSON string. For details on defining anchor properties, refer to
Manage comments and replies
. |
| author | object (
User
)
Output only. The author of the comment. The author's email address and permission ID will not be populated. |
| deleted | boolean
Output only. Whether the comment has been deleted. A deleted comment has no content. |
| htmlContent | string
Output only. The content of the comment with HTML formatting. |
| content | string
The plain text content of the comment. This field is used for setting the content, while
htmlContent
should be displayed. |
| quotedFileContent | object
The file content to which the comment refers, typically within the anchor region. For a text file, for example, this would be the text at the location of the comment. |
| quotedFileContent.mimeType | string
The MIME type of the quoted content. |
| quotedFileContent.value | string
The quoted content itself. This is interpreted as plain text if set through the API. |
| assigneeEmailAddress | string
Output only. The email address of the user assigned to this comment. If no user is assigned, the field is unset. |

object (
Reply
)

Output only. The full list of replies to the comment in chronological order.

string

Output only. A list of email addresses for users mentioned in this comment. If no users are mentioned, the list is empty.

Output only. The ID of the comment.

Output only. Identifies what kind of resource this is. Value: the fixed string
"drive#comment"
.

Output only. The time at which the comment was created (RFC 3339 date-time).

Output only. The last time the comment or any of its replies was modified (RFC 3339 date-time).

boolean

Output only. Whether the comment has been resolved by one of its replies.

A region of the document represented as a JSON string. For details on defining anchor properties, refer to
Manage comments and replies
.

object (
User
)

Output only. The author of the comment. The author's email address and permission ID will not be populated.

Output only. Whether the comment has been deleted. A deleted comment has no content.

Output only. The content of the comment with HTML formatting.

The plain text content of the comment. This field is used for setting the content, while
htmlContent
should be displayed.

object

The file content to which the comment refers, typically within the anchor region. For a text file, for example, this would be the text at the location of the comment.

The MIME type of the quoted content.

The quoted content itself. This is interpreted as plain text if set through the API.

Output only. The email address of the user assigned to this comment. If no user is assigned, the field is unset.


| Methods |  |
| --- | --- |
| create | Creates a comment on a file. |
| delete | Deletes a comment. |
| get | Gets a comment by ID. |
| list | Lists a file's comments. |
| update | Updates a comment with patch semantics. |


## Methods


### create


### delete


### get


### list


### update

Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2025-11-06 UTC.


---

# Method: comments.create Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/reference/rest/v3/comments/create

- Home
- Google Workspace
- Google Drive
- Reference
- HTTP request
- Path parameters
- Request body
- Response body
- Authorization scopes
- Try it!
Creates a comment on a file. For more information, see
Manage comments and replies
.

Required: The
fields
parameter must be set. To return the exact fields you need, see
Return specific fields
.


### HTTP request

POST https://www.googleapis.com/drive/v3/files/{fileId}/comments

The URL uses
gRPC Transcoding
syntax.


### Path parameters


| Parameters |  |
| --- | --- |
| fileId | string
The ID of the file. |

string

The ID of the file.


### Request body

The request body contains an instance of
Comment
.


### Response body

If successful, the response body contains a newly created instance of
Comment
.


### Authorization scopes

Requires one of the following OAuth scopes:

- https://www.googleapis.com/auth/drive
- https://www.googleapis.com/auth/drive.file
Some scopes are restricted and require a security assessment for your app to use them. For more information, see the
Authorization guide
.

Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2025-04-18 UTC.


---

# Method: comments.delete Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/reference/rest/v3/comments/delete

- Home
- Google Workspace
- Google Drive
- Reference
- HTTP request
- Path parameters
- Request body
- Response body
- Authorization scopes
- Try it!
Deletes a comment. For more information, see
Manage comments and replies
.


### HTTP request

DELETE https://www.googleapis.com/drive/v3/files/{fileId}/comments/{commentId}

The URL uses
gRPC Transcoding
syntax.


### Path parameters


| Parameters |  |
| --- | --- |
| fileId | string
The ID of the file. |
| commentId | string
The ID of the comment. |

string

The ID of the file.

The ID of the comment.


### Request body

The request body must be empty.


### Response body

If successful, the response body is an empty JSON object.


### Authorization scopes

Requires one of the following OAuth scopes:

- https://www.googleapis.com/auth/drive
- https://www.googleapis.com/auth/drive.file
Some scopes are restricted and require a security assessment for your app to use them. For more information, see the
Authorization guide
.

Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2025-05-09 UTC.


---

# Method: comments.get Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/reference/rest/v3/comments/get

- Home
- Google Workspace
- Google Drive
- Reference
- HTTP request
- Path parameters
- Query parameters
- Request body
- Response body
- Authorization scopes
- Try it!
Gets a comment by ID. For more information, see
Manage comments and replies
.

Required: The
fields
parameter must be set. To return the exact fields you need, see
Return specific fields
.


### HTTP request

GET https://www.googleapis.com/drive/v3/files/{fileId}/comments/{commentId}

The URL uses
gRPC Transcoding
syntax.


### Path parameters


| Parameters |  |
| --- | --- |
| fileId | string
The ID of the file. |
| commentId | string
The ID of the comment. |

string

The ID of the file.

The ID of the comment.


### Query parameters


| Parameters |  |
| --- | --- |
| includeDeleted | boolean
Whether to return deleted comments. Deleted comments will not include their original content. |

boolean

Whether to return deleted comments. Deleted comments will not include their original content.


### Request body

The request body must be empty.


### Response body

If successful, the response body contains an instance of
Comment
.


### Authorization scopes

Requires one of the following OAuth scopes:

- https://www.googleapis.com/auth/drive
- https://www.googleapis.com/auth/drive.file
- https://www.googleapis.com/auth/drive.meet.readonly
- https://www.googleapis.com/auth/drive.readonly
Some scopes are restricted and require a security assessment for your app to use them. For more information, see the
Authorization guide
.

Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2025-04-18 UTC.


---

# Method: comments.list Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/reference/rest/v3/comments/list

- Home
- Google Workspace
- Google Drive
- Reference
- HTTP request
- Path parameters
- Query parameters
- Request body
- Response body
JSON representation
- JSON representation
- Authorization scopes
- Try it!
Lists a file's comments. For more information, see
Manage comments and replies
.

Required: The
fields
parameter must be set. To return the exact fields you need, see
Return specific fields
.


### HTTP request

GET https://www.googleapis.com/drive/v3/files/{fileId}/comments

The URL uses
gRPC Transcoding
syntax.


### Path parameters


| Parameters |  |
| --- | --- |
| fileId | string
The ID of the file. |

string

The ID of the file.


### Query parameters


| Parameters |  |
| --- | --- |
| includeDeleted | boolean
Whether to include deleted comments. Deleted comments will not include their original content. |
| pageSize | integer
The maximum number of comments to return per page. |
| pageToken | string
The token for continuing a previous list request on the next page. This should be set to the value of 'nextPageToken' from the previous response. |
| startModifiedTime | string
The minimum value of 'modifiedTime' for the result comments (RFC 3339 date-time). |

boolean

Whether to include deleted comments. Deleted comments will not include their original content.

integer

The maximum number of comments to return per page.

The token for continuing a previous list request on the next page. This should be set to the value of 'nextPageToken' from the previous response.

The minimum value of 'modifiedTime' for the result comments (RFC 3339 date-time).


### Request body

The request body must be empty.


### Response body

A list of comments on a file.

If successful, the response body contains data with the following structure:


| JSON representation |
| --- |
| {
"comments"
:
[
{
object (
Comment
)
}
]
,
"kind"
:
string
,
"nextPageToken"
:
string
} |


```json
{
"comments"
:
[
{
object (
Comment
)
}
]
,
"kind"
:
string
,
"nextPageToken"
:
string
}
```


| Fields |  |
| --- | --- |
| comments[] | object (
Comment
)
The list of comments. If nextPageToken is populated, then this list may be incomplete and an additional page of results should be fetched. |
| kind | string
Identifies what kind of resource this is. Value: the fixed string
"drive#commentList"
. |
| nextPageToken | string
The page token for the next page of comments. This will be absent if the end of the comments list has been reached. If the token is rejected for any reason, it should be discarded, and pagination should be restarted from the first page of results. The page token is typically valid for several hours. However, if new items are added or removed, your expected results might differ. |

object (
Comment
)

The list of comments. If nextPageToken is populated, then this list may be incomplete and an additional page of results should be fetched.

Identifies what kind of resource this is. Value: the fixed string
"drive#commentList"
.

The page token for the next page of comments. This will be absent if the end of the comments list has been reached. If the token is rejected for any reason, it should be discarded, and pagination should be restarted from the first page of results. The page token is typically valid for several hours. However, if new items are added or removed, your expected results might differ.


### Authorization scopes

Requires one of the following OAuth scopes:

- https://www.googleapis.com/auth/drive
- https://www.googleapis.com/auth/drive.file
- https://www.googleapis.com/auth/drive.meet.readonly
- https://www.googleapis.com/auth/drive.readonly
Some scopes are restricted and require a security assessment for your app to use them. For more information, see the
Authorization guide
.

Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2025-07-23 UTC.


---

# Method: comments.update Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/reference/rest/v3/comments/update

- Home
- Google Workspace
- Google Drive
- Reference
- HTTP request
- Path parameters
- Request body
- Response body
- Authorization scopes
- Try it!
Updates a comment with patch semantics. For more information, see
Manage comments and replies
.

Required: The
fields
parameter must be set. To return the exact fields you need, see
Return specific fields
.


### HTTP request

PATCH https://www.googleapis.com/drive/v3/files/{fileId}/comments/{commentId}

The URL uses
gRPC Transcoding
syntax.


### Path parameters


| Parameters |  |
| --- | --- |
| fileId | string
The ID of the file. |
| commentId | string
The ID of the comment. |

string

The ID of the file.

The ID of the comment.


### Request body

The request body contains an instance of
Comment
.


### Response body

If successful, the response body contains an instance of
Comment
.


### Authorization scopes

Requires one of the following OAuth scopes:

- https://www.googleapis.com/auth/drive
- https://www.googleapis.com/auth/drive.file
Some scopes are restricted and require a security assessment for your app to use them. For more information, see the
Authorization guide
.

Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2025-04-18 UTC.


---

# REST Resource: drives Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/reference/rest/v3/drives

- Home
- Google Workspace
- Google Drive
- Reference
- Resource: Drive
JSON representation
- JSON representation
- Methods

## Resource: Drive

Representation of a shared drive.

Some resource methods (such as
drives.update
) require a
driveId
. Use the
drives.list
method to retrieve the ID for a shared drive.


| JSON representation |
| --- |
| {
"id"
:
string
,
"name"
:
string
,
"colorRgb"
:
string
,
"kind"
:
string
,
"backgroundImageLink"
:
string
,
"capabilities"
:
{
"canAddChildren"
:
boolean
,
"canComment"
:
boolean
,
"canCopy"
:
boolean
,
"canDeleteDrive"
:
boolean
,
"canDownload"
:
boolean
,
"canEdit"
:
boolean
,
"canListChildren"
:
boolean
,
"canManageMembers"
:
boolean
,
"canReadRevisions"
:
boolean
,
"canRename"
:
boolean
,
"canRenameDrive"
:
boolean
,
"canChangeDriveBackground"
:
boolean
,
"canShare"
:
boolean
,
"canChangeCopyRequiresWriterPermissionRestriction"
:
boolean
,
"canChangeDomainUsersOnlyRestriction"
:
boolean
,
"canChangeDriveMembersOnlyRestriction"
:
boolean
,
"canChangeSharingFoldersRequiresOrganizerPermissionRestriction"
:
boolean
,
"canResetDriveRestrictions"
:
boolean
,
"canDeleteChildren"
:
boolean
,
"canTrashChildren"
:
boolean
,
"canChangeDownloadRestriction"
:
boolean
}
,
"themeId"
:
string
,
"backgroundImageFile"
:
{
"id"
:
string
,
"xCoordinate"
:
number
,
"yCoordinate"
:
number
,
"width"
:
number
}
,
"createdTime"
:
string
,
"hidden"
:
boolean
,
"restrictions"
:
{
"copyRequiresWriterPermission"
:
boolean
,
"domainUsersOnly"
:
boolean
,
"driveMembersOnly"
:
boolean
,
"adminManagedRestrictions"
:
boolean
,
"sharingFoldersRequiresOrganizerPermission"
:
boolean
,
"downloadRestriction"
:
{
object (
DownloadRestriction
)
}
}
,
"orgUnitId"
:
string
} |


```json
{
"id"
:
string
,
"name"
:
string
,
"colorRgb"
:
string
,
"kind"
:
string
,
"backgroundImageLink"
:
string
,
"capabilities"
:
{
"canAddChildren"
:
boolean
,
"canComment"
:
boolean
,
"canCopy"
:
boolean
,
"canDeleteDrive"
:
boolean
,
"canDownload"
:
boolean
,
"canEdit"
:
boolean
,
"canListChildren"
:
boolean
,
"canManageMembers"
:
boolean
,
"canReadRevisions"
:
boolean
,
"canRename"
:
boolean
,
"canRenameDrive"
:
boolean
,
"canChangeDriveBackground"
:
boolean
,
"canShare"
:
boolean
,
"canChangeCopyRequiresWriterPermissionRestriction"
:
boolean
,
"canChangeDomainUsersOnlyRestriction"
:
boolean
,
"canChangeDriveMembersOnlyRestriction"
:
boolean
,
"canChangeSharingFoldersRequiresOrganizerPermissionRestriction"
:
boolean
,
"canResetDriveRestrictions"
:
boolean
,
"canDeleteChildren"
:
boolean
,
"canTrashChildren"
:
boolean
,
"canChangeDownloadRestriction"
:
boolean
}
,
"themeId"
:
string
,
"backgroundImageFile"
:
{
"id"
:
string
,
"xCoordinate"
:
number
,
"yCoordinate"
:
number
,
"width"
:
number
}
,
"createdTime"
:
string
,
"hidden"
:
boolean
,
"restrictions"
:
{
"copyRequiresWriterPermission"
:
boolean
,
"domainUsersOnly"
:
boolean
,
"driveMembersOnly"
:
boolean
,
"adminManagedRestrictions"
:
boolean
,
"sharingFoldersRequiresOrganizerPermission"
:
boolean
,
"downloadRestriction"
:
{
object (
DownloadRestriction
)
}
}
,
"orgUnitId"
:
string
}
```


| Fields |  |
| --- | --- |
| id | string
Output only. The ID of this shared drive which is also the ID of the top level folder of this shared drive. |
| name | string
The name of this shared drive. |
| colorRgb | string
The color of this shared drive as an RGB hex string. It can only be set on a
drive.drives.update
request that does not set
themeId
. |
| kind | string
Output only. Identifies what kind of resource this is. Value: the fixed string
"drive#drive"
. |
| backgroundImageLink | string
Output only. A short-lived link to this shared drive's background image. |
| capabilities | object
Output only. Capabilities the current user has on this shared drive. |
| capabilities.canAddChildren | boolean
Output only. Whether the current user can add children to folders in this shared drive. |
| capabilities.canComment | boolean
Output only. Whether the current user can comment on files in this shared drive. |
| capabilities.canCopy | boolean
Output only. Whether the current user can copy files in this shared drive. |
| capabilities.canDeleteDrive | boolean
Output only. Whether the current user can delete this shared drive. Attempting to delete the shared drive may still fail if there are untrashed items inside the shared drive. |
| capabilities.canDownload | boolean
Output only. Whether the current user can download files in this shared drive. |
| capabilities.canEdit | boolean
Output only. Whether the current user can edit files in this shared drive |
| capabilities.canListChildren | boolean
Output only. Whether the current user can list the children of folders in this shared drive. |
| capabilities.canManageMembers | boolean
Output only. Whether the current user can add members to this shared drive or remove them or change their role. |
| capabilities.canReadRevisions | boolean
Output only. Whether the current user can read the revisions resource of files in this shared drive. |
| capabilities.canRename | boolean
Output only. Whether the current user can rename files or folders in this shared drive. |
| capabilities.canRenameDrive | boolean
Output only. Whether the current user can rename this shared drive. |
| capabilities.canChangeDriveBackground | boolean
Output only. Whether the current user can change the background of this shared drive. |
| capabilities.canShare | boolean
Output only. Whether the current user can share files or folders in this shared drive. |
| capabilities.canChangeCopyRequiresWriterPermissionRestriction | boolean
Output only. Whether the current user can change the
copyRequiresWriterPermission
restriction of this shared drive. |
| capabilities.canChangeDomainUsersOnlyRestriction | boolean
Output only. Whether the current user can change the
domainUsersOnly
restriction of this shared drive. |
| capabilities.canChangeDriveMembersOnlyRestriction | boolean
Output only. Whether the current user can change the
driveMembersOnly
restriction of this shared drive. |
| capabilities.canChangeSharingFoldersRequiresOrganizerPermissionRestriction | boolean
Output only. Whether the current user can change the
sharingFoldersRequiresOrganizerPermission
restriction of this shared drive. |
| capabilities.canResetDriveRestrictions | boolean
Output only. Whether the current user can reset the shared drive restrictions to defaults. |
| capabilities.canDeleteChildren | boolean
Output only. Whether the current user can delete children from folders in this shared drive. |
| capabilities.canTrashChildren | boolean
Output only. Whether the current user can trash children from folders in this shared drive. |
| capabilities.canChangeDownloadRestriction | boolean
Output only. Whether the current user can change organizer-applied download restrictions of this shared drive. |
| themeId | string
The ID of the theme from which the background image and color will be set. The set of possible
driveThemes
can be retrieved from a
drive.about.get
response. When not specified on a
drive.drives.create
request, a random theme is chosen from which the background image and color are set. This is a write-only field; it can only be set on requests that don't set
colorRgb
or
backgroundImageFile
. |
| backgroundImageFile | object
An image file and cropping parameters from which a background image for this shared drive is set. This is a write only field; it can only be set on
drive.drives.update
requests that don't set
themeId
. When specified, all fields of the
backgroundImageFile
must be set. |
| backgroundImageFile.id | string
The ID of an image file in Google Drive to use for the background image. |
| backgroundImageFile.xCoordinate | number
The X coordinate of the upper left corner of the cropping area in the background image. This is a value in the closed range of 0 to 1. This value represents the horizontal distance from the left side of the entire image to the left side of the cropping area divided by the width of the entire image. |
| backgroundImageFile.yCoordinate | number
The Y coordinate of the upper left corner of the cropping area in the background image. This is a value in the closed range of 0 to 1. This value represents the vertical distance from the top side of the entire image to the top side of the cropping area divided by the height of the entire image. |
| backgroundImageFile.width | number
The width of the cropped image in the closed range of 0 to 1. This value represents the width of the cropped image divided by the width of the entire image. The height is computed by applying a width to height aspect ratio of 80 to 9. The resulting image must be at least 1280 pixels wide and 144 pixels high. |
| createdTime | string
Output only. The time at which the shared drive was created (RFC 3339 date-time). |
| hidden | boolean
Whether the shared drive is hidden from default view. |
| restrictions | object
A set of restrictions that apply to this shared drive or items inside this shared drive. Note that restrictions can't be set when creating a shared drive. To add a restriction, first create a shared drive and then use
drives.update
to add restrictions. |
| restrictions.copyRequiresWriterPermission | boolean
Whether the options to copy, print, or download files inside this shared drive, should be disabled for readers and commenters. When this restriction is set to
true
, it will override the similarly named field to
true
for any file inside this shared drive. |
| restrictions.domainUsersOnly | boolean
Whether access to this shared drive and items inside this shared drive is restricted to users of the domain to which this shared drive belongs. This restriction may be overridden by other sharing policies controlled outside of this shared drive. |
| restrictions.driveMembersOnly | boolean
Whether access to items inside this shared drive is restricted to its members. |
| restrictions.adminManagedRestrictions | boolean
Whether administrative privileges on this shared drive are required to modify restrictions. |
| restrictions.sharingFoldersRequiresOrganizerPermission | boolean
If true, only users with the organizer role can share folders. If false, users with either the organizer role or the file organizer role can share folders. |
| restrictions.downloadRestriction | object (
DownloadRestriction
)
Download restrictions applied by shared drive managers. |
| orgUnitId | string
Output only. The organizational unit of this shared drive. This field is only populated on
drives.list
responses when the
useDomainAdminAccess
parameter is set to
true
. |

string

Output only. The ID of this shared drive which is also the ID of the top level folder of this shared drive.

The name of this shared drive.

The color of this shared drive as an RGB hex string. It can only be set on a
drive.drives.update
request that does not set
themeId
.

Output only. Identifies what kind of resource this is. Value: the fixed string
"drive#drive"
.

Output only. A short-lived link to this shared drive's background image.

object

Output only. Capabilities the current user has on this shared drive.

boolean

Output only. Whether the current user can add children to folders in this shared drive.

Output only. Whether the current user can comment on files in this shared drive.

Output only. Whether the current user can copy files in this shared drive.

Output only. Whether the current user can delete this shared drive. Attempting to delete the shared drive may still fail if there are untrashed items inside the shared drive.

Output only. Whether the current user can download files in this shared drive.

Output only. Whether the current user can edit files in this shared drive

Output only. Whether the current user can list the children of folders in this shared drive.

Output only. Whether the current user can add members to this shared drive or remove them or change their role.

Output only. Whether the current user can read the revisions resource of files in this shared drive.

Output only. Whether the current user can rename files or folders in this shared drive.

Output only. Whether the current user can rename this shared drive.

Output only. Whether the current user can change the background of this shared drive.

Output only. Whether the current user can share files or folders in this shared drive.

Output only. Whether the current user can change the
copyRequiresWriterPermission
restriction of this shared drive.

Output only. Whether the current user can change the
domainUsersOnly
restriction of this shared drive.

Output only. Whether the current user can change the
driveMembersOnly
restriction of this shared drive.

Output only. Whether the current user can change the
sharingFoldersRequiresOrganizerPermission
restriction of this shared drive.

Output only. Whether the current user can reset the shared drive restrictions to defaults.

Output only. Whether the current user can delete children from folders in this shared drive.

Output only. Whether the current user can trash children from folders in this shared drive.

Output only. Whether the current user can change organizer-applied download restrictions of this shared drive.

The ID of the theme from which the background image and color will be set. The set of possible
driveThemes
can be retrieved from a
drive.about.get
response. When not specified on a
drive.drives.create
request, a random theme is chosen from which the background image and color are set. This is a write-only field; it can only be set on requests that don't set
colorRgb
or
backgroundImageFile
.

An image file and cropping parameters from which a background image for this shared drive is set. This is a write only field; it can only be set on
drive.drives.update
requests that don't set
themeId
. When specified, all fields of the
backgroundImageFile
must be set.

The ID of an image file in Google Drive to use for the background image.

number

The X coordinate of the upper left corner of the cropping area in the background image. This is a value in the closed range of 0 to 1. This value represents the horizontal distance from the left side of the entire image to the left side of the cropping area divided by the width of the entire image.

The Y coordinate of the upper left corner of the cropping area in the background image. This is a value in the closed range of 0 to 1. This value represents the vertical distance from the top side of the entire image to the top side of the cropping area divided by the height of the entire image.

The width of the cropped image in the closed range of 0 to 1. This value represents the width of the cropped image divided by the width of the entire image. The height is computed by applying a width to height aspect ratio of 80 to 9. The resulting image must be at least 1280 pixels wide and 144 pixels high.

Output only. The time at which the shared drive was created (RFC 3339 date-time).

Whether the shared drive is hidden from default view.

A set of restrictions that apply to this shared drive or items inside this shared drive. Note that restrictions can't be set when creating a shared drive. To add a restriction, first create a shared drive and then use
drives.update
to add restrictions.

Whether the options to copy, print, or download files inside this shared drive, should be disabled for readers and commenters. When this restriction is set to
true
, it will override the similarly named field to
true
for any file inside this shared drive.

Whether access to this shared drive and items inside this shared drive is restricted to users of the domain to which this shared drive belongs. This restriction may be overridden by other sharing policies controlled outside of this shared drive.

Whether access to items inside this shared drive is restricted to its members.

Whether administrative privileges on this shared drive are required to modify restrictions.

If true, only users with the organizer role can share folders. If false, users with either the organizer role or the file organizer role can share folders.

object (
DownloadRestriction
)

Download restrictions applied by shared drive managers.

Output only. The organizational unit of this shared drive. This field is only populated on
drives.list
responses when the
useDomainAdminAccess
parameter is set to
true
.


| Methods |  |
| --- | --- |
| create | Creates a shared drive. |
| delete | Permanently deletes a shared drive for which the user is an
organizer
. |
| get | Gets a shared drive's metadata by ID. |
| hide | Hides a shared drive from the default view. |
| list | Lists the user's shared drives. |
| unhide | Restores a shared drive to the default view. |
| update | Updates the metadata for a shared drive. |


## Methods


### create


### delete


### get


### hide


### list

Lists the user's shared drives.


### unhide


### update

Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2025-07-16 UTC.


---

# Method: drives.create Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/reference/rest/v3/drives/create

- Home
- Google Workspace
- Google Drive
- Reference
- HTTP request
- Query parameters
- Request body
- Response body
- Authorization scopes
- Try it!
Creates a shared drive. For more information, see
Manage shared drives
.


### HTTP request

POST https://www.googleapis.com/drive/v3/drives

The URL uses
gRPC Transcoding
syntax.


### Query parameters


| Parameters |  |
| --- | --- |
| requestId | string
Required. An ID, such as a random UUID, which uniquely identifies this user's request for idempotent creation of a shared drive. A repeated request by the same user and with the same request ID will avoid creating duplicates by attempting to create the same shared drive. If the shared drive already exists a 409 error will be returned. |

string

Required. An ID, such as a random UUID, which uniquely identifies this user's request for idempotent creation of a shared drive. A repeated request by the same user and with the same request ID will avoid creating duplicates by attempting to create the same shared drive. If the shared drive already exists a 409 error will be returned.


### Request body

The request body contains an instance of
Drive
.


### Response body

If successful, the response body contains a newly created instance of
Drive
.


### Authorization scopes

Requires the following OAuth scope:

- https://www.googleapis.com/auth/drive
Some scopes are restricted and require a security assessment for your app to use them. For more information, see the
Authorization guide
.

Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2025-08-13 UTC.


---

# Method: drives.delete Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/reference/rest/v3/drives/delete

- Home
- Google Workspace
- Google Drive
- Reference
- HTTP request
- Path parameters
- Query parameters
- Request body
- Response body
- Authorization scopes
- Try it!
Permanently deletes a shared drive for which the user is an
organizer
. The shared drive cannot contain any untrashed items. For more information, see
Manage shared drives
.


### HTTP request

DELETE https://www.googleapis.com/drive/v3/drives/{driveId}

The URL uses
gRPC Transcoding
syntax.


### Path parameters


| Parameters |  |
| --- | --- |
| driveId | string
The ID of the shared drive. |

string

The ID of the shared drive.


### Query parameters


| Parameters |  |
| --- | --- |
| useDomainAdminAccess | boolean
Issue the request as a domain administrator; if set to true, then the requester will be granted access if they are an administrator of the domain to which the shared drive belongs. |
| allowItemDeletion | boolean
Whether any items inside the shared drive should also be deleted. This option is only supported when
useDomainAdminAccess
is also set to
true
. |

boolean

Issue the request as a domain administrator; if set to true, then the requester will be granted access if they are an administrator of the domain to which the shared drive belongs.

Whether any items inside the shared drive should also be deleted. This option is only supported when
useDomainAdminAccess
is also set to
true
.


### Request body

The request body must be empty.


### Response body

If successful, the response body is an empty JSON object.


### Authorization scopes

Requires the following OAuth scope:

- https://www.googleapis.com/auth/drive
Some scopes are restricted and require a security assessment for your app to use them. For more information, see the
Authorization guide
.

Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2025-08-13 UTC.


---

# Method: drives.get Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/reference/rest/v3/drives/get

- Home
- Google Workspace
- Google Drive
- Reference
- HTTP request
- Path parameters
- Query parameters
- Request body
- Response body
- Authorization scopes
- Try it!
Gets a shared drive's metadata by ID. For more information, see
Manage shared drives
.


### HTTP request

GET https://www.googleapis.com/drive/v3/drives/{driveId}

The URL uses
gRPC Transcoding
syntax.


### Path parameters


| Parameters |  |
| --- | --- |
| driveId | string
The ID of the shared drive. |

string

The ID of the shared drive.


### Query parameters


| Parameters |  |
| --- | --- |
| useDomainAdminAccess | boolean
Issue the request as a domain administrator; if set to true, then the requester will be granted access if they are an administrator of the domain to which the shared drive belongs. |

boolean

Issue the request as a domain administrator; if set to true, then the requester will be granted access if they are an administrator of the domain to which the shared drive belongs.


### Request body

The request body must be empty.


### Response body

If successful, the response body contains an instance of
Drive
.


### Authorization scopes

Requires one of the following OAuth scopes:

- https://www.googleapis.com/auth/drive
- https://www.googleapis.com/auth/drive.readonly
Some scopes are restricted and require a security assessment for your app to use them. For more information, see the
Authorization guide
.

Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2025-08-13 UTC.


---

# Method: drives.hide Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/reference/rest/v3/drives/hide

- Home
- Google Workspace
- Google Drive
- Reference
- HTTP request
- Path parameters
- Request body
- Response body
- Authorization scopes
- Try it!
Hides a shared drive from the default view. For more information, see
Manage shared drives
.


### HTTP request

POST https://www.googleapis.com/drive/v3/drives/{driveId}/hide

The URL uses
gRPC Transcoding
syntax.


### Path parameters


| Parameters |  |
| --- | --- |
| driveId | string
The ID of the shared drive. |

string

The ID of the shared drive.


### Request body

The request body must be empty.


### Response body

If successful, the response body contains an instance of
Drive
.


### Authorization scopes

Requires the following OAuth scope:

- https://www.googleapis.com/auth/drive
Some scopes are restricted and require a security assessment for your app to use them. For more information, see the
Authorization guide
.

Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2025-08-13 UTC.


---

# Method: drives.list Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/reference/rest/v3/drives/list

- Home
- Google Workspace
- Google Drive
- Reference
- HTTP request
- Query parameters
- Request body
- Response body
JSON representation
- JSON representation
- Authorization scopes
- Try it!
Lists the user's shared drives.
This method accepts the
q
parameter, which is a search query combining one or more search terms. For more information, see the
Search for shared drives
guide.

This method accepts the
q
parameter, which is a search query combining one or more search terms. For more information, see the
Search for shared drives
guide.


### HTTP request

GET https://www.googleapis.com/drive/v3/drives

The URL uses
gRPC Transcoding
syntax.


### Query parameters


| Parameters |  |
| --- | --- |
| pageSize | integer
Maximum number of shared drives to return per page. |
| pageToken | string
Page token for shared drives. |
| q | string
Query string for searching shared drives. |
| useDomainAdminAccess | boolean
Issue the request as a domain administrator; if set to true, then all shared drives of the domain in which the requester is an administrator are returned. |

integer

Maximum number of shared drives to return per page.

string

Page token for shared drives.

Query string for searching shared drives.

boolean

Issue the request as a domain administrator; if set to true, then all shared drives of the domain in which the requester is an administrator are returned.


### Request body

The request body must be empty.


### Response body

A list of shared drives.

If successful, the response body contains data with the following structure:


| JSON representation |
| --- |
| {
"drives"
:
[
{
object (
Drive
)
}
]
,
"nextPageToken"
:
string
,
"kind"
:
string
} |


```json
{
"drives"
:
[
{
object (
Drive
)
}
]
,
"nextPageToken"
:
string
,
"kind"
:
string
}
```


| Fields |  |
| --- | --- |
| drives[] | object (
Drive
)
The list of shared drives. If nextPageToken is populated, then this list may be incomplete and an additional page of results should be fetched. |
| nextPageToken | string
The page token for the next page of shared drives. This will be absent if the end of the list has been reached. If the token is rejected for any reason, it should be discarded, and pagination should be restarted from the first page of results. The page token is typically valid for several hours. However, if new items are added or removed, your expected results might differ. |
| kind | string
Identifies what kind of resource this is. Value: the fixed string
"drive#driveList"
. |

object (
Drive
)

The list of shared drives. If nextPageToken is populated, then this list may be incomplete and an additional page of results should be fetched.

The page token for the next page of shared drives. This will be absent if the end of the list has been reached. If the token is rejected for any reason, it should be discarded, and pagination should be restarted from the first page of results. The page token is typically valid for several hours. However, if new items are added or removed, your expected results might differ.

Identifies what kind of resource this is. Value: the fixed string
"drive#driveList"
.


### Authorization scopes

Requires one of the following OAuth scopes:

- https://www.googleapis.com/auth/drive
- https://www.googleapis.com/auth/drive.readonly
Some scopes are restricted and require a security assessment for your app to use them. For more information, see the
Authorization guide
.

Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2026-03-20 UTC.


---

# Method: drives.unhide Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/reference/rest/v3/drives/unhide

- Home
- Google Workspace
- Google Drive
- Reference
- HTTP request
- Path parameters
- Request body
- Response body
- Authorization scopes
- Try it!
Restores a shared drive to the default view. For more information, see
Manage shared drives
.


### HTTP request

POST https://www.googleapis.com/drive/v3/drives/{driveId}/unhide

The URL uses
gRPC Transcoding
syntax.


### Path parameters


| Parameters |  |
| --- | --- |
| driveId | string
The ID of the shared drive. |

string

The ID of the shared drive.


### Request body

The request body must be empty.


### Response body

If successful, the response body contains an instance of
Drive
.


### Authorization scopes

Requires the following OAuth scope:

- https://www.googleapis.com/auth/drive
Some scopes are restricted and require a security assessment for your app to use them. For more information, see the
Authorization guide
.

Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2025-08-13 UTC.


---

# Method: drives.update Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/reference/rest/v3/drives/update

- Home
- Google Workspace
- Google Drive
- Reference
- HTTP request
- Path parameters
- Query parameters
- Request body
- Response body
- Authorization scopes
- Try it!
Updates the metadata for a shared drive. For more information, see
Manage shared drives
.


### HTTP request

PATCH https://www.googleapis.com/drive/v3/drives/{driveId}

The URL uses
gRPC Transcoding
syntax.


### Path parameters


| Parameters |  |
| --- | --- |
| driveId | string
The ID of the shared drive. |

string

The ID of the shared drive.


### Query parameters


| Parameters |  |
| --- | --- |
| useDomainAdminAccess | boolean
Issue the request as a domain administrator; if set to true, then the requester will be granted access if they are an administrator of the domain to which the shared drive belongs. |

boolean

Issue the request as a domain administrator; if set to true, then the requester will be granted access if they are an administrator of the domain to which the shared drive belongs.


### Request body

The request body contains an instance of
Drive
.


### Response body

If successful, the response body contains an instance of
Drive
.


### Authorization scopes

Requires the following OAuth scope:

- https://www.googleapis.com/auth/drive
Some scopes are restricted and require a security assessment for your app to use them. For more information, see the
Authorization guide
.

Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2025-08-13 UTC.


---

# REST Resource: files Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/reference/rest/v3/files

- Home
- Google Workspace
- Google Drive
- Reference
- Resource: File
JSON representation
JSON representation
JSON representation
ContentRestriction
JSON representation
DownloadRestrictionsMetadata
JSON representation
DownloadRestriction
JSON representation
ClientEncryptionDetails
JSON representation
DecryptionMetadata
JSON representation
- JSON representation
JSON representation
JSON representation
- JSON representation
- ContentRestriction
JSON representation
- DownloadRestrictionsMetadata
JSON representation
- DownloadRestriction
JSON representation
- ClientEncryptionDetails
JSON representation
- DecryptionMetadata
JSON representation
- Methods

## Resource: File

The metadata for a file.

Some resource methods (such as
files.update
) require a
fileId
. Use the
files.list
method to retrieve the ID for a file.


| JSON representation |
| --- |
| {
"kind"
:
string
,
"driveId"
:
string
,
"fileExtension"
:
string
,
"copyRequiresWriterPermission"
:
boolean
,
"md5Checksum"
:
string
,
"contentHints"
:
{
"indexableText"
:
string
,
"thumbnail"
:
{
"image"
:
string
,
"mimeType"
:
string
}
}
,
"writersCanShare"
:
boolean
,
"viewedByMe"
:
boolean
,
"mimeType"
:
string
,
"exportLinks"
:
{
string
:
string
,
...
}
,
"parents"
:
[
string
]
,
"thumbnailLink"
:
string
,
"iconLink"
:
string
,
"shared"
:
boolean
,
"lastModifyingUser"
:
{
object (
User
)
}
,
"owners"
:
[
{
object (
User
)
}
]
,
"headRevisionId"
:
string
,
"sharingUser"
:
{
object (
User
)
}
,
"webViewLink"
:
string
,
"webContentLink"
:
string
,
"size"
:
string
,
"viewersCanCopyContent"
:
boolean
,
"permissions"
:
[
{
object (
Permission
)
}
]
,
"hasThumbnail"
:
boolean
,
"spaces"
:
[
string
]
,
"folderColorRgb"
:
string
,
"id"
:
string
,
"name"
:
string
,
"description"
:
string
,
"starred"
:
boolean
,
"trashed"
:
boolean
,
"explicitlyTrashed"
:
boolean
,
"createdTime"
:
string
,
"modifiedTime"
:
string
,
"modifiedByMeTime"
:
string
,
"viewedByMeTime"
:
string
,
"sharedWithMeTime"
:
string
,
"quotaBytesUsed"
:
string
,
"version"
:
string
,
"originalFilename"
:
string
,
"ownedByMe"
:
boolean
,
"fullFileExtension"
:
string
,
"properties"
:
{
string
:
value
,
...
}
,
"appProperties"
:
{
string
:
value
,
...
}
,
"isAppAuthorized"
:
boolean
,
"teamDriveId"
:
string
,
"capabilities"
:
{
"canChangeViewersCanCopyContent"
:
boolean
,
"canMoveChildrenOutOfDrive"
:
boolean
,
"canReadDrive"
:
boolean
,
"canEdit"
:
boolean
,
"canCopy"
:
boolean
,
"canComment"
:
boolean
,
"canAddChildren"
:
boolean
,
"canDelete"
:
boolean
,
"canDownload"
:
boolean
,
"canListChildren"
:
boolean
,
"canRemoveChildren"
:
boolean
,
"canRename"
:
boolean
,
"canTrash"
:
boolean
,
"canReadRevisions"
:
boolean
,
"canReadTeamDrive"
:
boolean
,
"canMoveTeamDriveItem"
:
boolean
,
"canChangeCopyRequiresWriterPermission"
:
boolean
,
"canMoveItemIntoTeamDrive"
:
boolean
,
"canUntrash"
:
boolean
,
"canModifyContent"
:
boolean
,
"canMoveItemWithinTeamDrive"
:
boolean
,
"canMoveItemOutOfTeamDrive"
:
boolean
,
"canDeleteChildren"
:
boolean
,
"canMoveChildrenOutOfTeamDrive"
:
boolean
,
"canMoveChildrenWithinTeamDrive"
:
boolean
,
"canTrashChildren"
:
boolean
,
"canMoveItemOutOfDrive"
:
boolean
,
"canAddMyDriveParent"
:
boolean
,
"canRemoveMyDriveParent"
:
boolean
,
"canMoveItemWithinDrive"
:
boolean
,
"canShare"
:
boolean
,
"canMoveChildrenWithinDrive"
:
boolean
,
"canModifyContentRestriction"
:
boolean
,
"canAddFolderFromAnotherDrive"
:
boolean
,
"canChangeSecurityUpdateEnabled"
:
boolean
,
"canAcceptOwnership"
:
boolean
,
"canReadLabels"
:
boolean
,
"canModifyLabels"
:
boolean
,
"canModifyEditorContentRestriction"
:
boolean
,
"canModifyOwnerContentRestriction"
:
boolean
,
"canRemoveContentRestriction"
:
boolean
,
"canDisableInheritedPermissions"
:
boolean
,
"canEnableInheritedPermissions"
:
boolean
,
"canChangeItemDownloadRestriction"
:
boolean
,
"canStartApproval"
:
boolean
}
,
"hasAugmentedPermissions"
:
boolean
,
"trashingUser"
:
{
object (
User
)
}
,
"thumbnailVersion"
:
string
,
"trashedTime"
:
string
,
"modifiedByMe"
:
boolean
,
"permissionIds"
:
[
string
]
,
"imageMediaMetadata"
:
{
"flashUsed"
:
boolean
,
"meteringMode"
:
string
,
"sensor"
:
string
,
"exposureMode"
:
string
,
"colorSpace"
:
string
,
"whiteBalance"
:
string
,
"width"
:
integer
,
"height"
:
integer
,
"location"
:
{
"latitude"
:
number
,
"longitude"
:
number
,
"altitude"
:
number
}
,
"rotation"
:
integer
,
"time"
:
string
,
"cameraMake"
:
string
,
"cameraModel"
:
string
,
"exposureTime"
:
number
,
"aperture"
:
number
,
"focalLength"
:
number
,
"isoSpeed"
:
integer
,
"exposureBias"
:
number
,
"maxApertureValue"
:
number
,
"subjectDistance"
:
integer
,
"lens"
:
string
}
,
"videoMediaMetadata"
:
{
"width"
:
integer
,
"height"
:
integer
,
"durationMillis"
:
string
}
,
"shortcutDetails"
:
{
"targetId"
:
string
,
"targetMimeType"
:
string
,
"targetResourceKey"
:
string
}
,
"contentRestrictions"
:
[
{
object (
ContentRestriction
)
}
]
,
"resourceKey"
:
string
,
"linkShareMetadata"
:
{
"securityUpdateEligible"
:
boolean
,
"securityUpdateEnabled"
:
boolean
}
,
"labelInfo"
:
{
"labels"
:
[
{
object (
Label
)
}
]
}
,
"sha1Checksum"
:
string
,
"sha256Checksum"
:
string
,
"inheritedPermissionsDisabled"
:
boolean
,
"downloadRestrictions"
:
{
object (
DownloadRestrictionsMetadata
)
}
,
"clientEncryptionDetails"
:
{
object (
ClientEncryptionDetails
)
}
} |


```json
{
"kind"
:
string
,
"driveId"
:
string
,
"fileExtension"
:
string
,
"copyRequiresWriterPermission"
:
boolean
,
"md5Checksum"
:
string
,
"contentHints"
:
{
"indexableText"
:
string
,
"thumbnail"
:
{
"image"
:
string
,
"mimeType"
:
string
}
}
,
"writersCanShare"
:
boolean
,
"viewedByMe"
:
boolean
,
"mimeType"
:
string
,
"exportLinks"
:
{
string
:
string
,
...
}
,
"parents"
:
[
string
]
,
"thumbnailLink"
:
string
,
"iconLink"
:
string
,
"shared"
:
boolean
,
"lastModifyingUser"
:
{
object (
User
)
}
,
"owners"
:
[
{
object (
User
)
}
]
,
"headRevisionId"
:
string
,
"sharingUser"
:
{
object (
User
)
}
,
"webViewLink"
:
string
,
"webContentLink"
:
string
,
"size"
:
string
,
"viewersCanCopyContent"
:
boolean
,
"permissions"
:
[
{
object (
Permission
)
}
]
,
"hasThumbnail"
:
boolean
,
"spaces"
:
[
string
]
,
"folderColorRgb"
:
string
,
"id"
:
string
,
"name"
:
string
,
"description"
:
string
,
"starred"
:
boolean
,
"trashed"
:
boolean
,
"explicitlyTrashed"
:
boolean
,
"createdTime"
:
string
,
"modifiedTime"
:
string
,
"modifiedByMeTime"
:
string
,
"viewedByMeTime"
:
string
,
"sharedWithMeTime"
:
string
,
"quotaBytesUsed"
:
string
,
"version"
:
string
,
"originalFilename"
:
string
,
"ownedByMe"
:
boolean
,
"fullFileExtension"
:
string
,
"properties"
:
{
string
:
value
,
...
}
,
"appProperties"
:
{
string
:
value
,
...
}
,
"isAppAuthorized"
:
boolean
,
"teamDriveId"
:
string
,
"capabilities"
:
{
"canChangeViewersCanCopyContent"
:
boolean
,
"canMoveChildrenOutOfDrive"
:
boolean
,
"canReadDrive"
:
boolean
,
"canEdit"
:
boolean
,
"canCopy"
:
boolean
,
"canComment"
:
boolean
,
"canAddChildren"
:
boolean
,
"canDelete"
:
boolean
,
"canDownload"
:
boolean
,
"canListChildren"
:
boolean
,
"canRemoveChildren"
:
boolean
,
"canRename"
:
boolean
,
"canTrash"
:
boolean
,
"canReadRevisions"
:
boolean
,
"canReadTeamDrive"
:
boolean
,
"canMoveTeamDriveItem"
:
boolean
,
"canChangeCopyRequiresWriterPermission"
:
boolean
,
"canMoveItemIntoTeamDrive"
:
boolean
,
"canUntrash"
:
boolean
,
"canModifyContent"
:
boolean
,
"canMoveItemWithinTeamDrive"
:
boolean
,
"canMoveItemOutOfTeamDrive"
:
boolean
,
"canDeleteChildren"
:
boolean
,
"canMoveChildrenOutOfTeamDrive"
:
boolean
,
"canMoveChildrenWithinTeamDrive"
:
boolean
,
"canTrashChildren"
:
boolean
,
"canMoveItemOutOfDrive"
:
boolean
,
"canAddMyDriveParent"
:
boolean
,
"canRemoveMyDriveParent"
:
boolean
,
"canMoveItemWithinDrive"
:
boolean
,
"canShare"
:
boolean
,
"canMoveChildrenWithinDrive"
:
boolean
,
"canModifyContentRestriction"
:
boolean
,
"canAddFolderFromAnotherDrive"
:
boolean
,
"canChangeSecurityUpdateEnabled"
:
boolean
,
"canAcceptOwnership"
:
boolean
,
"canReadLabels"
:
boolean
,
"canModifyLabels"
:
boolean
,
"canModifyEditorContentRestriction"
:
boolean
,
"canModifyOwnerContentRestriction"
:
boolean
,
"canRemoveContentRestriction"
:
boolean
,
"canDisableInheritedPermissions"
:
boolean
,
"canEnableInheritedPermissions"
:
boolean
,
"canChangeItemDownloadRestriction"
:
boolean
,
"canStartApproval"
:
boolean
}
,
"hasAugmentedPermissions"
:
boolean
,
"trashingUser"
:
{
object (
User
)
}
,
"thumbnailVersion"
:
string
,
"trashedTime"
:
string
,
"modifiedByMe"
:
boolean
,
"permissionIds"
:
[
string
]
,
"imageMediaMetadata"
:
{
"flashUsed"
:
boolean
,
"meteringMode"
:
string
,
"sensor"
:
string
,
"exposureMode"
:
string
,
"colorSpace"
:
string
,
"whiteBalance"
:
string
,
"width"
:
integer
,
"height"
:
integer
,
"location"
:
{
"latitude"
:
number
,
"longitude"
:
number
,
"altitude"
:
number
}
,
"rotation"
:
integer
,
"time"
:
string
,
"cameraMake"
:
string
,
"cameraModel"
:
string
,
"exposureTime"
:
number
,
"aperture"
:
number
,
"focalLength"
:
number
,
"isoSpeed"
:
integer
,
"exposureBias"
:
number
,
"maxApertureValue"
:
number
,
"subjectDistance"
:
integer
,
"lens"
:
string
}
,
"videoMediaMetadata"
:
{
"width"
:
integer
,
"height"
:
integer
,
"durationMillis"
:
string
}
,
"shortcutDetails"
:
{
"targetId"
:
string
,
"targetMimeType"
:
string
,
"targetResourceKey"
:
string
}
,
"contentRestrictions"
:
[
{
object (
ContentRestriction
)
}
]
,
"resourceKey"
:
string
,
"linkShareMetadata"
:
{
"securityUpdateEligible"
:
boolean
,
"securityUpdateEnabled"
:
boolean
}
,
"labelInfo"
:
{
"labels"
:
[
{
object (
Label
)
}
]
}
,
"sha1Checksum"
:
string
,
"sha256Checksum"
:
string
,
"inheritedPermissionsDisabled"
:
boolean
,
"downloadRestrictions"
:
{
object (
DownloadRestrictionsMetadata
)
}
,
"clientEncryptionDetails"
:
{
object (
ClientEncryptionDetails
)
}
}
```


| Fields |  |
| --- | --- |
| kind | string
Output only. Identifies what kind of resource this is. Value: the fixed string
"drive#file"
. |
| driveId | string
Output only. ID of the shared drive the file resides in. Only populated for items in shared drives. |
| fileExtension | string
Output only. The final component of
fullFileExtension
. This is only available for files with binary content in Google Drive. |
| copyRequiresWriterPermission | boolean
Whether the options to copy, print, or download this file should be disabled for readers and commenters. |
| md5Checksum | string
Output only. The MD5 checksum for the content of the file. This is only applicable to files with binary content in Google Drive. |
| contentHints | object
Additional information about the content of the file. These fields are never populated in responses. |
| contentHints.indexableText | string
Text to be indexed for the file to improve fullText queries. This is limited to 128 KB in length and may contain HTML elements. |
| contentHints.thumbnail | object
A thumbnail for the file. This will only be used if Google Drive cannot generate a standard thumbnail. |
| contentHints.thumbnail.image | string (
bytes
format)
The thumbnail data encoded with URL-safe Base64 (
RFC 4648 section 5
).
A base64-encoded string. |
| contentHints.thumbnail.mimeType | string
The MIME type of the thumbnail. |
| writersCanShare | boolean
Whether users with only
writer
permission can modify the file's permissions. Not populated for items in shared drives. |
| viewedByMe | boolean
Output only. Whether the file has been viewed by this user. |
| mimeType | string
The MIME type of the file.
Google Drive attempts to automatically detect an appropriate value from uploaded content, if no value is provided. The value cannot be changed unless a new revision is uploaded.
If a file is created with a Google Doc MIME type, the uploaded content is imported, if possible. The supported import formats are published in the
about
resource. |
| exportLinks | map (key: string, value: string)
Output only. Links for exporting Docs Editors files to specific formats.
An object containing a list of
"key": value
pairs. Example:
{ "name": "wrench", "mass": "1.3kg", "count": "3" }
. |
| parents[] | string
The ID of the parent folder containing the file.
A file can only have one parent folder; specifying multiple parents isn't supported.
If not specified as part of a create request, the file is placed directly in the user's My Drive folder. If not specified as part of a copy request, the file inherits any discoverable parent of the source file. Update requests must use the
addParents
and
removeParents
parameters to modify the parents list. |
| thumbnailLink | string
Output only. A short-lived link to the file's thumbnail, if available. Typically lasts on the order of hours. Not intended for direct usage on web applications due to
Cross-Origin Resource Sharing (CORS)
policies. Consider using a proxy server. Only populated when the requesting app can access the file's content. If the file isn't shared publicly, the URL returned in
files.thumbnailLink
must be fetched using a credentialed request. |
| iconLink | string
Output only. A static, unauthenticated link to the file's icon. |
| shared | boolean
Output only. Whether the file has been shared. Not populated for items in shared drives. |
| lastModifyingUser | object (
User
)
Output only. The last user to modify the file. This field is only populated when the last modification was performed by a signed-in user. |
| owners[] | object (
User
)
Output only. The owner of this file. Only certain legacy files may have more than one owner. This field isn't populated for items in shared drives. |
| headRevisionId | string
Output only. The ID of the file's head revision. This is currently only available for files with binary content in Google Drive. |
| sharingUser | object (
User
)
Output only. The user who shared the file with the requesting user, if applicable. |
| webViewLink | string
Output only. A link for opening the file in a relevant Google editor or viewer in a browser. |
| webContentLink | string
Output only. A link for downloading the content of the file in a browser. This is only available for files with binary content in Google Drive. |
| size | string (
int64
format)
Output only. Size in bytes of blobs and Google Workspace editor files. Won't be populated for files that have no size, like shortcuts and folders. |
| viewersCanCopyContent
(deprecated) | boolean
Deprecated: Use
copyRequiresWriterPermission
instead. |
| permissions[] | object (
Permission
)
Output only. The full list of permissions for the file. This is only available if the requesting user can share the file. Not populated for items in shared drives. |
| hasThumbnail | boolean
Output only. Whether this file has a thumbnail. This doesn't indicate whether the requesting app has access to the thumbnail. To check access, look for the presence of the thumbnailLink field. |
| spaces[] | string
Output only. The list of spaces which contain the file. The currently supported values are
drive
,
appDataFolder
, and
photos
. |
| folderColorRgb | string
The color for a folder or a shortcut to a folder as an RGB hex string. The supported colors are published in the
folderColorPalette
field of the
about
resource.
If an unsupported color is specified, the closest color in the palette is used instead. |
| id | string
The ID of the file. |
| name | string
The name of the file. This isn't necessarily unique within a folder. Note that for immutable items such as the top-level folders of shared drives, the My Drive root folder, and the Application Data folder, the name is constant. |
| description | string
A short description of the file. |
| starred | boolean
Whether the user has starred the file. |
| trashed | boolean
Whether the file has been trashed, either explicitly or from a trashed parent folder. Only the owner may trash a file, but other users can still access the file in the owner's trash until it's permanently deleted. |
| explicitlyTrashed | boolean
Output only. Whether the file has been explicitly trashed, as opposed to recursively trashed from a parent folder. |
| createdTime | string
The time at which the file was created (
RFC 3339 date-time
). |
| modifiedTime | string
The last time the file was modified by anyone (
RFC 3339 date-time
).
Note that setting
modifiedTime
also updates
modifiedByMeTime
for the user. |
| modifiedByMeTime | string
Output only. The last time the file was modified by the user (
RFC 3339 date-time
). |
| viewedByMeTime | string
The last time the file was viewed by the user (
RFC 3339 date-time
). |
| sharedWithMeTime | string
Output only. The time at which the file was shared with the user, if applicable (
RFC 3339 date-time
). |
| quotaBytesUsed | string (
int64
format)
Output only. The number of storage quota bytes used by the file. This includes the head revision as well as previous revisions with
keepForever
enabled. |
| version | string (
int64
format)
Output only. A monotonically increasing version number for the file. This reflects every change made to the file on the server, even those not visible to the user. |
| originalFilename | string
The original filename of the uploaded content if available, or else the original value of the
name
field. This is only available for files with binary content in Google Drive. |
| ownedByMe | boolean
Output only. Whether the user owns the file. Not populated for items in shared drives. |
| fullFileExtension | string
Output only. The full file extension extracted from the
name
field. May contain multiple concatenated extensions, such as "tar.gz". This is only available for files with binary content in Google Drive.
This is automatically updated when the
name
field changes, however it's not cleared if the new name doesn't contain a valid extension. |
| properties | map (key: string, value: value (
Value
format))
A collection of arbitrary key-value pairs which are visible to all apps.
Entries with null values are cleared in update and copy requests.
An object containing a list of
"key": value
pairs. Example:
{ "name": "wrench", "mass": "1.3kg", "count": "3" }
. |
| appProperties | map (key: string, value: value (
Value
format))
A collection of arbitrary key-value pairs which are private to the requesting app.
Entries with null values are cleared in update and copy requests.
These properties can only be retrieved using an authenticated request. An authenticated request uses an access token obtained with an OAuth 2.0 client ID. You cannot use an API key to retrieve private properties.
An object containing a list of
"key": value
pairs. Example:
{ "name": "wrench", "mass": "1.3kg", "count": "3" }
. |
| isAppAuthorized | boolean
Output only. Whether the file was created or opened by the requesting app. |
| teamDriveId
(deprecated) | string
Deprecated: Output only. Use
driveId
instead. |
| capabilities | object
Output only. Capabilities the current user has on this file. Each capability corresponds to a fine-grained action that a user may take. For more information, see
Understand file capabilities
. |
| capabilities.canChangeViewersCanCopyContent
(deprecated) | boolean
Deprecated: Output only. |
| capabilities.canMoveChildrenOutOfDrive | boolean
Output only. Whether the current user can move children of this folder outside of the shared drive. This is
false
when the item isn't a folder. Only populated for items in shared drives. |
| capabilities.canReadDrive | boolean
Output only. Whether the current user can read the shared drive to which this file belongs. Only populated for items in shared drives. |
| capabilities.canEdit | boolean
Output only. Whether the current user can edit this file. Other factors may limit the type of changes a user can make to a file. For example, see
canChangeCopyRequiresWriterPermission
or
canModifyContent
. |
| capabilities.canCopy | boolean
Output only. Whether the current user can copy this file. For an item in a shared drive, whether the current user can copy non-folder descendants of this item, or this item if it's not a folder. |
| capabilities.canComment | boolean
Output only. Whether the current user can comment on this file. |
| capabilities.canAddChildren | boolean
Output only. Whether the current user can add children to this folder. This is always
false
when the item isn't a folder. |
| capabilities.canDelete | boolean
Output only. Whether the current user can delete this file. |
| capabilities.canDownload | boolean
Output only. Whether the current user can download this file. |
| capabilities.canListChildren | boolean
Output only. Whether the current user can list the children of this folder. This is always
false
when the item isn't a folder. |
| capabilities.canRemoveChildren | boolean
Output only. Whether the current user can remove children from this folder. This is always
false
when the item isn't a folder. For a folder in a shared drive, use
canDeleteChildren
or
canTrashChildren
instead. |
| capabilities.canRename | boolean
Output only. Whether the current user can rename this file. |
| capabilities.canTrash | boolean
Output only. Whether the current user can move this file to trash. |
| capabilities.canReadRevisions | boolean
Output only. Whether the current user can read the revisions resource of this file. For a shared drive item, whether revisions of non-folder descendants of this item, or this item if it's not a folder, can be read. |
| capabilities.canReadTeamDrive
(deprecated) | boolean
Deprecated: Output only. Use
canReadDrive
instead. |
| capabilities.canMoveTeamDriveItem
(deprecated) | boolean
Deprecated: Output only. Use
canMoveItemWithinDrive
or
canMoveItemOutOfDrive
instead. |
| capabilities.canChangeCopyRequiresWriterPermission | boolean
Output only. Whether the current user can change the
copyRequiresWriterPermission
restriction of this file. |
| capabilities.canMoveItemIntoTeamDrive
(deprecated) | boolean
Deprecated: Output only. Use
canMoveItemOutOfDrive
instead. |
| capabilities.canUntrash | boolean
Output only. Whether the current user can restore this file from trash. |
| capabilities.canModifyContent | boolean
Output only. Whether the current user can modify the content of this file. |
| capabilities.canMoveItemWithinTeamDrive
(deprecated) | boolean
Deprecated: Output only. Use
canMoveItemWithinDrive
instead. |
| capabilities.canMoveItemOutOfTeamDrive
(deprecated) | boolean
Deprecated: Output only. Use
canMoveItemOutOfDrive
instead. |
| capabilities.canDeleteChildren | boolean
Output only. Whether the current user can delete children of this folder. This is
false
when the item isn't a folder. Only populated for items in shared drives. |
| capabilities.canMoveChildrenOutOfTeamDrive
(deprecated) | boolean
Deprecated: Output only. Use
canMoveChildrenOutOfDrive
instead. |
| capabilities.canMoveChildrenWithinTeamDrive
(deprecated) | boolean
Deprecated: Output only. Use
canMoveChildrenWithinDrive
instead. |
| capabilities.canTrashChildren | boolean
Output only. Whether the current user can trash children of this folder. This is
false
when the item isn't a folder. Only populated for items in shared drives. |
| capabilities.canMoveItemOutOfDrive | boolean
Output only. Whether the current user can move this item outside of this drive by changing its parent. Note that a request to change the parent of the item may still fail depending on the new parent that's being added. |
| capabilities.canAddMyDriveParent | boolean
Output only. Whether the current user can add a parent for the item without removing an existing parent in the same request. Not populated for shared drive files. |
| capabilities.canRemoveMyDriveParent | boolean
Output only. Whether the current user can remove a parent from the item without adding another parent in the same request. Not populated for shared drive files. |
| capabilities.canMoveItemWithinDrive | boolean
Output only. Whether the current user can move this item within this drive. Note that a request to change the parent of the item may still fail depending on the new parent that's being added and the parent that is being removed. |
| capabilities.canShare | boolean
Output only. Whether the current user can modify the sharing settings for this file. |
| capabilities.canMoveChildrenWithinDrive | boolean
Output only. Whether the current user can move children of this folder within this drive. This is
false
when the item isn't a folder. Note that a request to move the child may still fail depending on the current user's access to the child and to the destination folder. |
| capabilities.canModifyContentRestriction
(deprecated) | boolean
Deprecated: Output only. Use one of
canModifyEditorContentRestriction
,
canModifyOwnerContentRestriction
, or
canRemoveContentRestriction
. |
| capabilities.canAddFolderFromAnotherDrive | boolean
Output only. Whether the current user can add a folder from another drive (different shared drive or My Drive) to this folder. This is
false
when the item isn't a folder. Only populated for items in shared drives. |
| capabilities.canChangeSecurityUpdateEnabled | boolean
Output only. Whether the current user can change the
securityUpdateEnabled
field on link share metadata. |
| capabilities.canAcceptOwnership | boolean
Output only. Whether the current user is the pending owner of the file. Not populated for shared drive files. |
| capabilities.canReadLabels | boolean
Output only. Whether the current user can read the labels on the file. |
| capabilities.canModifyLabels | boolean
Output only. Whether the current user can modify the labels on the file. |
| capabilities.canModifyEditorContentRestriction | boolean
Output only. Whether the current user can add or modify content restrictions on the file which are editor restricted. |
| capabilities.canModifyOwnerContentRestriction | boolean
Output only. Whether the current user can add or modify content restrictions which are owner restricted. |
| capabilities.canRemoveContentRestriction | boolean
Output only. Whether there's a content restriction on the file that can be removed by the current user. |
| capabilities.canDisableInheritedPermissions | boolean
Whether a user can disable inherited permissions. |
| capabilities.canEnableInheritedPermissions | boolean
Whether a user can re-enable inherited permissions. |
| capabilities.canChangeItemDownloadRestriction | boolean
Output only. Whether the current user can change the owner or organizer-applied download restrictions of the file. |
| capabilities.canStartApproval | boolean
Whether the current user can start an approval on the file. |
| hasAugmentedPermissions | boolean
Output only. Whether there are permissions directly on this file. This field is only populated for items in shared drives. |
| trashingUser | object (
User
)
Output only. If the file has been explicitly trashed, the user who trashed it. Only populated for items in shared drives. |
| thumbnailVersion | string (
int64
format)
Output only. The thumbnail version for use in thumbnail cache invalidation. |
| trashedTime | string
Output only. The time that the item was trashed (
RFC 3339 date-time
). Only populated for items in shared drives. |
| modifiedByMe | boolean
Output only. Whether the file has been modified by this user. |
| permissionIds[] | string
Output only. List of permission IDs for users with access to this file. |
| imageMediaMetadata | object
Output only. Additional metadata about image media, if available. |
| imageMediaMetadata.flashUsed | boolean
Output only. Whether a flash was used to create the photo. |
| imageMediaMetadata.meteringMode | string
Output only. The metering mode used to create the photo. |
| imageMediaMetadata.sensor | string
Output only. The type of sensor used to create the photo. |
| imageMediaMetadata.exposureMode | string
Output only. The exposure mode used to create the photo. |
| imageMediaMetadata.colorSpace | string
Output only. The color space of the photo. |
| imageMediaMetadata.whiteBalance | string
Output only. The white balance mode used to create the photo. |
| imageMediaMetadata.width | integer
Output only. The width of the image in pixels. |
| imageMediaMetadata.height | integer
Output only. The height of the image in pixels. |
| imageMediaMetadata.location | object
Output only. Geographic location information stored in the image. |
| imageMediaMetadata.location.latitude | number
Output only. The latitude stored in the image. |
| imageMediaMetadata.location.longitude | number
Output only. The longitude stored in the image. |
| imageMediaMetadata.location.altitude | number
Output only. The altitude stored in the image. |
| imageMediaMetadata.rotation | integer
Output only. The number of clockwise 90 degree rotations applied from the image's original orientation. |
| imageMediaMetadata.time | string
Output only. The date and time the photo was taken (EXIF DateTime). |
| imageMediaMetadata.cameraMake | string
Output only. The make of the camera used to create the photo. |
| imageMediaMetadata.cameraModel | string
Output only. The model of the camera used to create the photo. |
| imageMediaMetadata.exposureTime | number
Output only. The length of the exposure, in seconds. |
| imageMediaMetadata.aperture | number
Output only. The aperture used to create the photo (f-number). |
| imageMediaMetadata.focalLength | number
Output only. The focal length used to create the photo, in millimeters. |
| imageMediaMetadata.isoSpeed | integer
Output only. The ISO speed used to create the photo. |
| imageMediaMetadata.exposureBias | number
Output only. The exposure bias of the photo (APEX value). |
| imageMediaMetadata.maxApertureValue | number
Output only. The smallest f-number of the lens at the focal length used to create the photo (APEX value). |
| imageMediaMetadata.subjectDistance | integer
Output only. The distance to the subject of the photo, in meters. |
| imageMediaMetadata.lens | string
Output only. The lens used to create the photo. |
| videoMediaMetadata | object
Output only. Additional metadata about video media. This may not be available immediately upon upload. |
| videoMediaMetadata.width | integer
Output only. The width of the video in pixels. |
| videoMediaMetadata.height | integer
Output only. The height of the video in pixels. |
| videoMediaMetadata.durationMillis | string (
int64
format)
Output only. The duration of the video in milliseconds. |
| shortcutDetails | object
Shortcut file details. Only populated for shortcut files, which have the mimeType field set to
application/vnd.google-apps.shortcut
. Can only be set on
files.create
requests. |
| shortcutDetails.targetId | string
The ID of the file that this shortcut points to. Can only be set on
files.create
requests. |
| shortcutDetails.targetMimeType | string
Output only. The MIME type of the file that this shortcut points to. The value of this field is a snapshot of the target's MIME type, captured when the shortcut is created. |
| shortcutDetails.targetResourceKey | string
Output only. The
resourceKey
for the target file. |
| contentRestrictions[] | object (
ContentRestriction
)
Restrictions for accessing the content of the file. Only populated if such a restriction exists. |
| resourceKey | string
Output only. A key needed to access the item via a shared link. |
| linkShareMetadata | object
Output only. LinkShare related details. Contains details about the link URLs that clients are using to refer to this item. |
| linkShareMetadata.securityUpdateEligible | boolean
Output only. Whether the file is eligible for security update. |
| linkShareMetadata.securityUpdateEnabled | boolean
Output only. Whether the security update is enabled for this file. |
| labelInfo | object
Output only. An overview of the labels on the file. |
| labelInfo.labels[] | object (
Label
)
Output only. The set of labels on the file as requested by the label IDs in the
includeLabels
parameter. By default, no labels are returned. |
| sha1Checksum | string
Output only. The SHA1 checksum associated with this file, if available. This field is only populated for files with content stored in Google Drive; it's not populated for Docs Editors or shortcut files. |
| sha256Checksum | string
Output only. The SHA256 checksum associated with this file, if available. This field is only populated for files with content stored in Google Drive; it's not populated for Docs Editors or shortcut files. |
| inheritedPermissionsDisabled | boolean
Whether this file has inherited permissions disabled. Inherited permissions are enabled by default. |
| downloadRestrictions | object (
DownloadRestrictionsMetadata
)
Download restrictions applied on the file. |
| clientEncryptionDetails | object (
ClientEncryptionDetails
)
Client Side Encryption related details. Contains details about the encryption state of the file and details regarding the encryption mechanism that clients need to use when decrypting the contents of this item. This will only be present on files and not on folders or shortcuts. |

string

Output only. Identifies what kind of resource this is. Value: the fixed string
"drive#file"
.

Output only. ID of the shared drive the file resides in. Only populated for items in shared drives.

Output only. The final component of
fullFileExtension
. This is only available for files with binary content in Google Drive.

boolean

Whether the options to copy, print, or download this file should be disabled for readers and commenters.

Output only. The MD5 checksum for the content of the file. This is only applicable to files with binary content in Google Drive.

object

Additional information about the content of the file. These fields are never populated in responses.

Text to be indexed for the file to improve fullText queries. This is limited to 128 KB in length and may contain HTML elements.

A thumbnail for the file. This will only be used if Google Drive cannot generate a standard thumbnail.

string (
bytes
format)

The thumbnail data encoded with URL-safe Base64 (
RFC 4648 section 5
).

A base64-encoded string.

The MIME type of the thumbnail.

Whether users with only
writer
permission can modify the file's permissions. Not populated for items in shared drives.

Output only. Whether the file has been viewed by this user.

The MIME type of the file.

Google Drive attempts to automatically detect an appropriate value from uploaded content, if no value is provided. The value cannot be changed unless a new revision is uploaded.

If a file is created with a Google Doc MIME type, the uploaded content is imported, if possible. The supported import formats are published in the
about
resource.

map (key: string, value: string)

Output only. Links for exporting Docs Editors files to specific formats.

An object containing a list of
"key": value
pairs. Example:
{ "name": "wrench", "mass": "1.3kg", "count": "3" }
.

The ID of the parent folder containing the file.

A file can only have one parent folder; specifying multiple parents isn't supported.

If not specified as part of a create request, the file is placed directly in the user's My Drive folder. If not specified as part of a copy request, the file inherits any discoverable parent of the source file. Update requests must use the
addParents
and
removeParents
parameters to modify the parents list.

Output only. A short-lived link to the file's thumbnail, if available. Typically lasts on the order of hours. Not intended for direct usage on web applications due to
Cross-Origin Resource Sharing (CORS)
policies. Consider using a proxy server. Only populated when the requesting app can access the file's content. If the file isn't shared publicly, the URL returned in
files.thumbnailLink
must be fetched using a credentialed request.

Output only. A static, unauthenticated link to the file's icon.

Output only. Whether the file has been shared. Not populated for items in shared drives.

object (
User
)

Output only. The last user to modify the file. This field is only populated when the last modification was performed by a signed-in user.

Output only. The owner of this file. Only certain legacy files may have more than one owner. This field isn't populated for items in shared drives.

Output only. The ID of the file's head revision. This is currently only available for files with binary content in Google Drive.

Output only. The user who shared the file with the requesting user, if applicable.

Output only. A link for opening the file in a relevant Google editor or viewer in a browser.

Output only. A link for downloading the content of the file in a browser. This is only available for files with binary content in Google Drive.

string (
int64
format)

Output only. Size in bytes of blobs and Google Workspace editor files. Won't be populated for files that have no size, like shortcuts and folders.

Deprecated: Use
copyRequiresWriterPermission
instead.

object (
Permission
)

Output only. The full list of permissions for the file. This is only available if the requesting user can share the file. Not populated for items in shared drives.

Output only. Whether this file has a thumbnail. This doesn't indicate whether the requesting app has access to the thumbnail. To check access, look for the presence of the thumbnailLink field.

Output only. The list of spaces which contain the file. The currently supported values are
drive
,
appDataFolder
, and
photos
.

The color for a folder or a shortcut to a folder as an RGB hex string. The supported colors are published in the
folderColorPalette
field of the
about
resource.

If an unsupported color is specified, the closest color in the palette is used instead.

The ID of the file.

The name of the file. This isn't necessarily unique within a folder. Note that for immutable items such as the top-level folders of shared drives, the My Drive root folder, and the Application Data folder, the name is constant.

A short description of the file.

Whether the user has starred the file.

Whether the file has been trashed, either explicitly or from a trashed parent folder. Only the owner may trash a file, but other users can still access the file in the owner's trash until it's permanently deleted.

Output only. Whether the file has been explicitly trashed, as opposed to recursively trashed from a parent folder.

The time at which the file was created (
RFC 3339 date-time
).

The last time the file was modified by anyone (
RFC 3339 date-time
).

Note that setting
modifiedTime
also updates
modifiedByMeTime
for the user.

Output only. The last time the file was modified by the user (
RFC 3339 date-time
).

The last time the file was viewed by the user (
RFC 3339 date-time
).

Output only. The time at which the file was shared with the user, if applicable (
RFC 3339 date-time
).

Output only. The number of storage quota bytes used by the file. This includes the head revision as well as previous revisions with
keepForever
enabled.

Output only. A monotonically increasing version number for the file. This reflects every change made to the file on the server, even those not visible to the user.

The original filename of the uploaded content if available, or else the original value of the
name
field. This is only available for files with binary content in Google Drive.

Output only. Whether the user owns the file. Not populated for items in shared drives.

Output only. The full file extension extracted from the
name
field. May contain multiple concatenated extensions, such as "tar.gz". This is only available for files with binary content in Google Drive.

This is automatically updated when the
name
field changes, however it's not cleared if the new name doesn't contain a valid extension.

map (key: string, value: value (
Value
format))

A collection of arbitrary key-value pairs which are visible to all apps.

Entries with null values are cleared in update and copy requests.

A collection of arbitrary key-value pairs which are private to the requesting app.

These properties can only be retrieved using an authenticated request. An authenticated request uses an access token obtained with an OAuth 2.0 client ID. You cannot use an API key to retrieve private properties.

Output only. Whether the file was created or opened by the requesting app.

Deprecated: Output only. Use
driveId
instead.

Output only. Capabilities the current user has on this file. Each capability corresponds to a fine-grained action that a user may take. For more information, see
Understand file capabilities
.

Deprecated: Output only.

Output only. Whether the current user can move children of this folder outside of the shared drive. This is
false
when the item isn't a folder. Only populated for items in shared drives.

Output only. Whether the current user can read the shared drive to which this file belongs. Only populated for items in shared drives.

Output only. Whether the current user can edit this file. Other factors may limit the type of changes a user can make to a file. For example, see
canChangeCopyRequiresWriterPermission
or
canModifyContent
.

Output only. Whether the current user can copy this file. For an item in a shared drive, whether the current user can copy non-folder descendants of this item, or this item if it's not a folder.

Output only. Whether the current user can comment on this file.

Output only. Whether the current user can add children to this folder. This is always
false
when the item isn't a folder.

Output only. Whether the current user can delete this file.

Output only. Whether the current user can download this file.

Output only. Whether the current user can list the children of this folder. This is always
false
when the item isn't a folder.

Output only. Whether the current user can remove children from this folder. This is always
false
when the item isn't a folder. For a folder in a shared drive, use
canDeleteChildren
or
canTrashChildren
instead.

Output only. Whether the current user can rename this file.

Output only. Whether the current user can move this file to trash.

Output only. Whether the current user can read the revisions resource of this file. For a shared drive item, whether revisions of non-folder descendants of this item, or this item if it's not a folder, can be read.

Deprecated: Output only. Use
canReadDrive
instead.

Deprecated: Output only. Use
canMoveItemWithinDrive
or
canMoveItemOutOfDrive
instead.

Output only. Whether the current user can change the
copyRequiresWriterPermission
restriction of this file.

Deprecated: Output only. Use
canMoveItemOutOfDrive
instead.

Output only. Whether the current user can restore this file from trash.

Output only. Whether the current user can modify the content of this file.

Deprecated: Output only. Use
canMoveItemWithinDrive
instead.

Output only. Whether the current user can delete children of this folder. This is
false
when the item isn't a folder. Only populated for items in shared drives.

Deprecated: Output only. Use
canMoveChildrenOutOfDrive
instead.

Deprecated: Output only. Use
canMoveChildrenWithinDrive
instead.

Output only. Whether the current user can trash children of this folder. This is
false
when the item isn't a folder. Only populated for items in shared drives.

Output only. Whether the current user can move this item outside of this drive by changing its parent. Note that a request to change the parent of the item may still fail depending on the new parent that's being added.

Output only. Whether the current user can add a parent for the item without removing an existing parent in the same request. Not populated for shared drive files.

Output only. Whether the current user can remove a parent from the item without adding another parent in the same request. Not populated for shared drive files.

Output only. Whether the current user can move this item within this drive. Note that a request to change the parent of the item may still fail depending on the new parent that's being added and the parent that is being removed.

Output only. Whether the current user can modify the sharing settings for this file.

Output only. Whether the current user can move children of this folder within this drive. This is
false
when the item isn't a folder. Note that a request to move the child may still fail depending on the current user's access to the child and to the destination folder.

Deprecated: Output only. Use one of
canModifyEditorContentRestriction
,
canModifyOwnerContentRestriction
, or
canRemoveContentRestriction
.

Output only. Whether the current user can add a folder from another drive (different shared drive or My Drive) to this folder. This is
false
when the item isn't a folder. Only populated for items in shared drives.

Output only. Whether the current user can change the
securityUpdateEnabled
field on link share metadata.

Output only. Whether the current user is the pending owner of the file. Not populated for shared drive files.

Output only. Whether the current user can read the labels on the file.

Output only. Whether the current user can modify the labels on the file.

Output only. Whether the current user can add or modify content restrictions on the file which are editor restricted.

Output only. Whether the current user can add or modify content restrictions which are owner restricted.

Output only. Whether there's a content restriction on the file that can be removed by the current user.

Whether a user can disable inherited permissions.

Whether a user can re-enable inherited permissions.

Output only. Whether the current user can change the owner or organizer-applied download restrictions of the file.

Whether the current user can start an approval on the file.

Output only. Whether there are permissions directly on this file. This field is only populated for items in shared drives.

Output only. If the file has been explicitly trashed, the user who trashed it. Only populated for items in shared drives.

Output only. The thumbnail version for use in thumbnail cache invalidation.

Output only. The time that the item was trashed (
RFC 3339 date-time
). Only populated for items in shared drives.

Output only. Whether the file has been modified by this user.

Output only. List of permission IDs for users with access to this file.

Output only. Additional metadata about image media, if available.

Output only. Whether a flash was used to create the photo.

Output only. The metering mode used to create the photo.

Output only. The type of sensor used to create the photo.

Output only. The exposure mode used to create the photo.

Output only. The color space of the photo.

Output only. The white balance mode used to create the photo.

integer

Output only. The width of the image in pixels.

Output only. The height of the image in pixels.

Output only. Geographic location information stored in the image.

number

Output only. The latitude stored in the image.

Output only. The longitude stored in the image.

Output only. The altitude stored in the image.

Output only. The number of clockwise 90 degree rotations applied from the image's original orientation.

Output only. The date and time the photo was taken (EXIF DateTime).

Output only. The make of the camera used to create the photo.

Output only. The model of the camera used to create the photo.

Output only. The length of the exposure, in seconds.

Output only. The aperture used to create the photo (f-number).

Output only. The focal length used to create the photo, in millimeters.

Output only. The ISO speed used to create the photo.

Output only. The exposure bias of the photo (APEX value).

Output only. The smallest f-number of the lens at the focal length used to create the photo (APEX value).

Output only. The distance to the subject of the photo, in meters.

Output only. The lens used to create the photo.

Output only. Additional metadata about video media. This may not be available immediately upon upload.

Output only. The width of the video in pixels.

Output only. The height of the video in pixels.

Output only. The duration of the video in milliseconds.

Shortcut file details. Only populated for shortcut files, which have the mimeType field set to
application/vnd.google-apps.shortcut
. Can only be set on
files.create
requests.

The ID of the file that this shortcut points to. Can only be set on
files.create
requests.

Output only. The MIME type of the file that this shortcut points to. The value of this field is a snapshot of the target's MIME type, captured when the shortcut is created.

Output only. The
resourceKey
for the target file.

object (
ContentRestriction
)

Restrictions for accessing the content of the file. Only populated if such a restriction exists.

Output only. A key needed to access the item via a shared link.

Output only. LinkShare related details. Contains details about the link URLs that clients are using to refer to this item.

Output only. Whether the file is eligible for security update.

Output only. Whether the security update is enabled for this file.

Output only. An overview of the labels on the file.

object (
Label
)

Output only. The set of labels on the file as requested by the label IDs in the
includeLabels
parameter. By default, no labels are returned.

Output only. The SHA1 checksum associated with this file, if available. This field is only populated for files with content stored in Google Drive; it's not populated for Docs Editors or shortcut files.

Output only. The SHA256 checksum associated with this file, if available. This field is only populated for files with content stored in Google Drive; it's not populated for Docs Editors or shortcut files.

Whether this file has inherited permissions disabled. Inherited permissions are enabled by default.

object (
DownloadRestrictionsMetadata
)

Download restrictions applied on the file.

object (
ClientEncryptionDetails
)

Client Side Encryption related details. Contains details about the encryption state of the file and details regarding the encryption mechanism that clients need to use when decrypting the contents of this item. This will only be present on files and not on folders or shortcuts.


### ContentRestriction

A restriction for accessing the content of the file.


| JSON representation |
| --- |
| {
"readOnly"
:
boolean
,
"reason"
:
string
,
"type"
:
string
,
"restrictingUser"
:
{
object (
User
)
}
,
"restrictionTime"
:
string
,
"ownerRestricted"
:
boolean
,
"systemRestricted"
:
boolean
} |


```json
{
"readOnly"
:
boolean
,
"reason"
:
string
,
"type"
:
string
,
"restrictingUser"
:
{
object (
User
)
}
,
"restrictionTime"
:
string
,
"ownerRestricted"
:
boolean
,
"systemRestricted"
:
boolean
}
```


| Fields |  |
| --- | --- |
| readOnly | boolean
Whether the content of the file is read-only. If a file is read-only, a new revision of the file may not be added, comments may not be added or modified, and the title of the file may not be modified. |
| reason | string
Reason for why the content of the file is restricted. This is only mutable on requests that also set
readOnly=true
. |
| type | string
Output only. The type of the content restriction. Currently the only possible value is
globalContentRestriction
. |
| restrictingUser | object (
User
)
Output only. The user who set the content restriction. Only populated if
readOnly=true
. |
| restrictionTime | string
Output only. The time at which the content restriction was set (formatted
RFC 3339 date-time
). Only populated if
readOnly=true
. |
| ownerRestricted | boolean
Whether the content restriction can only be modified or removed by a user who owns the file. For files in shared drives, any user with
organizer
capabilities can modify or remove this content restriction. |
| systemRestricted | boolean
Output only. Whether the content restriction was applied by the system, for example due to an esignature. Users cannot modify or remove system restricted content restrictions. |

Whether the content of the file is read-only. If a file is read-only, a new revision of the file may not be added, comments may not be added or modified, and the title of the file may not be modified.

Reason for why the content of the file is restricted. This is only mutable on requests that also set
readOnly=true
.

Output only. The type of the content restriction. Currently the only possible value is
globalContentRestriction
.

Output only. The user who set the content restriction. Only populated if
readOnly=true
.

Output only. The time at which the content restriction was set (formatted
RFC 3339 date-time
). Only populated if
readOnly=true
.

Whether the content restriction can only be modified or removed by a user who owns the file. For files in shared drives, any user with
organizer
capabilities can modify or remove this content restriction.

Output only. Whether the content restriction was applied by the system, for example due to an esignature. Users cannot modify or remove system restricted content restrictions.


### DownloadRestrictionsMetadata

Download restrictions applied to the file.


| JSON representation |
| --- |
| {
"itemDownloadRestriction"
:
{
object (
DownloadRestriction
)
}
,
"effectiveDownloadRestrictionWithContext"
:
{
object (
DownloadRestriction
)
}
} |


```json
{
"itemDownloadRestriction"
:
{
object (
DownloadRestriction
)
}
,
"effectiveDownloadRestrictionWithContext"
:
{
object (
DownloadRestriction
)
}
}
```


| Fields |  |
| --- | --- |
| itemDownloadRestriction | object (
DownloadRestriction
)
The download restriction of the file applied directly by the owner or organizer. This doesn't take into account shared drive settings or DLP rules. |
| effectiveDownloadRestrictionWithContext | object (
DownloadRestriction
)
Output only. The effective download restriction applied to this file. This considers all restriction settings and DLP rules. |

object (
DownloadRestriction
)

The download restriction of the file applied directly by the owner or organizer. This doesn't take into account shared drive settings or DLP rules.

Output only. The effective download restriction applied to this file. This considers all restriction settings and DLP rules.


### DownloadRestriction

A restriction for copy and download of the file.


| JSON representation |
| --- |
| {
"restrictedForReaders"
:
boolean
,
"restrictedForWriters"
:
boolean
} |


```json
{
"restrictedForReaders"
:
boolean
,
"restrictedForWriters"
:
boolean
}
```


| Fields |  |
| --- | --- |
| restrictedForReaders | boolean
Whether download and copy is restricted for readers. |
| restrictedForWriters | boolean
Whether download and copy is restricted for writers. If true, download is also restricted for readers. |

Whether download and copy is restricted for readers.

Whether download and copy is restricted for writers. If true, download is also restricted for readers.


### ClientEncryptionDetails

Details about the client-side encryption applied to the file.


| JSON representation |
| --- |
| {
"encryptionState"
:
string
,
"decryptionMetadata"
:
{
object (
DecryptionMetadata
)
}
} |


```json
{
"encryptionState"
:
string
,
"decryptionMetadata"
:
{
object (
DecryptionMetadata
)
}
}
```


| Fields |  |
| --- | --- |
| encryptionState | string
The encryption state of the file. The values expected here are:
encrypted
unencrypted |
| decryptionMetadata | object (
DecryptionMetadata
)
The metadata used for client-side operations. |

The encryption state of the file. The values expected here are:

encrypted

unencrypted

object (
DecryptionMetadata
)

The metadata used for client-side operations.


### DecryptionMetadata

Representation of the CSE DecryptionMetadata.


| JSON representation |
| --- |
| {
"wrappedKey"
:
string
,
"kaclsId"
:
string
,
"kaclsName"
:
string
,
"aes256GcmChunkSize"
:
string
,
"jwt"
:
string
,
"keyFormat"
:
string
,
"encryptionResourceKeyHash"
:
string
} |


```json
{
"wrappedKey"
:
string
,
"kaclsId"
:
string
,
"kaclsName"
:
string
,
"aes256GcmChunkSize"
:
string
,
"jwt"
:
string
,
"keyFormat"
:
string
,
"encryptionResourceKeyHash"
:
string
}
```


| Fields |  |
| --- | --- |
| wrappedKey | string
The URL-safe Base64 encoded wrapped key used to encrypt the contents of the file. |
| kaclsId | string (
int64
format)
The ID of the KACLS (Key ACL Service) used to encrypt the file. |
| kaclsName | string
The name of the KACLS (Key ACL Service) used to encrypt the file. |
| aes256GcmChunkSize | string
Chunk size used if content was encrypted with the AES 256 GCM Cipher. Possible values are:
default
small |
| jwt | string
The signed JSON Web Token (JWT) which can be used to authorize the requesting user with the Key ACL Service (KACLS). The JWT asserts that the requesting user has at least read permissions on the file. |
| keyFormat | string
Key format for the unwrapped key. Must be
tinkAesGcmKey
. |
| encryptionResourceKeyHash | string
The URL-safe Base64 encoded HMAC-SHA256 digest of the resource metadata with its DEK (Data Encryption Key); see
https://developers.google.com/workspace/cse/reference |

The URL-safe Base64 encoded wrapped key used to encrypt the contents of the file.

The ID of the KACLS (Key ACL Service) used to encrypt the file.

The name of the KACLS (Key ACL Service) used to encrypt the file.

Chunk size used if content was encrypted with the AES 256 GCM Cipher. Possible values are:

default

small

The signed JSON Web Token (JWT) which can be used to authorize the requesting user with the Key ACL Service (KACLS). The JWT asserts that the requesting user has at least read permissions on the file.

Key format for the unwrapped key. Must be
tinkAesGcmKey
.

The URL-safe Base64 encoded HMAC-SHA256 digest of the resource metadata with its DEK (Data Encryption Key); see
https://developers.google.com/workspace/cse/reference


| Methods |  |
| --- | --- |
| copy | Creates a copy of a file and applies any requested updates with patch semantics. |
| create | Creates a file. |
| delete | Permanently deletes a file owned by the user without moving it to the trash. |
| download | Downloads the content of a file. |
| emptyTrash | Permanently deletes all of the user's trashed files. |
| export | Exports a Google Workspace document to the requested MIME type and returns exported byte content. |
| generateCseToken | Generates a CSE token which can be used to create or update CSE files. |
| generateIds | Generates a set of file IDs which can be provided in create or copy requests. |
| get | Gets a file's metadata or content by ID. |
| list | Lists the user's files. |
| listLabels | Lists the labels on a file. |
| modifyLabels | Modifies the set of labels applied to a file. |
| update | Updates a file's metadata, content, or both. |
| watch | Subscribes to changes to a file. |


## Methods


### copy


### create

Creates a file.


### delete


### download


### emptyTrash


### export


### generateCseToken


### generateIds


### get

Gets a file's metadata or content by ID.


### list

Lists the user's files.


### listLabels


### modifyLabels


### update

Updates a file's metadata, content, or both.


### watch

Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2026-05-01 UTC.


---

# Method: files.copy Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/reference/rest/v3/files/copy

- Home
- Google Workspace
- Google Drive
- Reference
- HTTP request
- Path parameters
- Query parameters
- Request body
- Response body
- Authorization scopes
- Try it!
Creates a copy of a file and applies any requested updates with patch semantics. For more information, see
Create and manage files
.


### HTTP request

POST https://www.googleapis.com/drive/v3/files/{fileId}/copy

The URL uses
gRPC Transcoding
syntax.


### Path parameters


| Parameters |  |
| --- | --- |
| fileId | string
The ID of the file. |

string

The ID of the file.


### Query parameters


| Parameters |  |
| --- | --- |
| enforceSingleParent
(deprecated) | boolean
Deprecated: Copying files into multiple folders is no longer supported. Use shortcuts instead. |
| ignoreDefaultVisibility | boolean
Whether to ignore the domain's default visibility settings for the created file. Domain administrators can choose to make all uploaded files visible to the domain by default; this parameter bypasses that behavior for the request. Permissions are still inherited from parent folders. |
| keepRevisionForever | boolean
Whether to set the
keepForever
field in the new head revision. This is only applicable to files with binary content in Google Drive. Only 200 revisions for the file can be kept forever. If the limit is reached, try deleting pinned revisions. |
| ocrLanguage | string
A language hint for OCR processing during image import (ISO 639-1 code). |
| supportsAllDrives | boolean
Whether the requesting application supports both My Drives and shared drives. |
| supportsTeamDrives
(deprecated) | boolean
Deprecated: Use
supportsAllDrives
instead. |
| includePermissionsForView | string
Specifies which additional view's permissions to include in the response. Only
published
is supported. |
| includeLabels | string
A comma-separated list of IDs of labels to include in the
labelInfo
part of the response. |

boolean

Deprecated: Copying files into multiple folders is no longer supported. Use shortcuts instead.

Whether to ignore the domain's default visibility settings for the created file. Domain administrators can choose to make all uploaded files visible to the domain by default; this parameter bypasses that behavior for the request. Permissions are still inherited from parent folders.

Whether to set the
keepForever
field in the new head revision. This is only applicable to files with binary content in Google Drive. Only 200 revisions for the file can be kept forever. If the limit is reached, try deleting pinned revisions.

A language hint for OCR processing during image import (ISO 639-1 code).

Whether the requesting application supports both My Drives and shared drives.

Deprecated: Use
supportsAllDrives
instead.

Specifies which additional view's permissions to include in the response. Only
published
is supported.

A comma-separated list of IDs of labels to include in the
labelInfo
part of the response.


### Request body

The request body contains an instance of
File
.


### Response body

If successful, the response body contains an instance of
File
.


### Authorization scopes

Requires one of the following OAuth scopes:

- https://www.googleapis.com/auth/drive
- https://www.googleapis.com/auth/drive.appdata
- https://www.googleapis.com/auth/drive.file
- https://www.googleapis.com/auth/drive.photos.readonly
Some scopes are restricted and require a security assessment for your app to use them. For more information, see the
Authorization guide
.

Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2025-08-26 UTC.


---

# Method: files.create Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/reference/rest/v3/files/create

- Home
- Google Workspace
- Google Drive
- Reference
- HTTP request
- Query parameters
- Request body
- Response body
- Authorization scopes
- Try it!
Creates a file. For more information, see
Create and manage files
.
This method supports an
/upload
URI and accepts uploaded media with the following characteristics:
Maximum file size:
5,120 GB
Accepted Media MIME types:
*/*
(Specify a valid MIME type, rather than the literal
*/*
value. The literal
*/*
is only used to indicate that any valid MIME type can be uploaded. For more information, see
Google Workspace and Google Drive supported MIME types
.)
For more information on uploading files, see
Upload file data
.
Apps creating shortcuts with the
create
method must specify the MIME type
application/vnd.google-apps.shortcut
.
Apps should specify a file extension in the
name
property when inserting files with the API. For example, an operation to insert a JPEG file should specify something like
"name": "cat.jpg"
in the metadata.
Subsequent
GET
requests include the read-only
fileExtension
property populated with the extension originally specified in the
name
property. When a Google Drive user requests to download a file, or when the file is downloaded through the sync client, Drive builds a full filename (with extension) based on the name. In cases where the extension is missing, Drive attempts to determine the extension based on the file's MIME type.

This method supports an
/upload
URI and accepts uploaded media with the following characteristics:
Maximum file size:
5,120 GB
Accepted Media MIME types:
*/*
(Specify a valid MIME type, rather than the literal
*/*
value. The literal
*/*
is only used to indicate that any valid MIME type can be uploaded. For more information, see
Google Workspace and Google Drive supported MIME types
.)
For more information on uploading files, see
Upload file data
.
Apps creating shortcuts with the
create
method must specify the MIME type
application/vnd.google-apps.shortcut
.
Apps should specify a file extension in the
name
property when inserting files with the API. For example, an operation to insert a JPEG file should specify something like
"name": "cat.jpg"
in the metadata.
Subsequent
GET
requests include the read-only
fileExtension
property populated with the extension originally specified in the
name
property. When a Google Drive user requests to download a file, or when the file is downloaded through the sync client, Drive builds a full filename (with extension) based on the name. In cases where the extension is missing, Drive attempts to determine the extension based on the file's MIME type.

- Maximum file size:
5,120 GB
- Accepted Media MIME types:
*/*
(Specify a valid MIME type, rather than the literal
*/*
value. The literal
*/*
is only used to indicate that any valid MIME type can be uploaded. For more information, see
Google Workspace and Google Drive supported MIME types
.)
(Specify a valid MIME type, rather than the literal
*/*
value. The literal
*/*
is only used to indicate that any valid MIME type can be uploaded. For more information, see
Google Workspace and Google Drive supported MIME types
.)

For more information on uploading files, see
Upload file data
.
Apps creating shortcuts with the
create
method must specify the MIME type
application/vnd.google-apps.shortcut
.
Apps should specify a file extension in the
name
property when inserting files with the API. For example, an operation to insert a JPEG file should specify something like
"name": "cat.jpg"
in the metadata.
Subsequent
GET
requests include the read-only
fileExtension
property populated with the extension originally specified in the
name
property. When a Google Drive user requests to download a file, or when the file is downloaded through the sync client, Drive builds a full filename (with extension) based on the name. In cases where the extension is missing, Drive attempts to determine the extension based on the file's MIME type.

Apps creating shortcuts with the
create
method must specify the MIME type
application/vnd.google-apps.shortcut
.
Apps should specify a file extension in the
name
property when inserting files with the API. For example, an operation to insert a JPEG file should specify something like
"name": "cat.jpg"
in the metadata.
Subsequent
GET
requests include the read-only
fileExtension
property populated with the extension originally specified in the
name
property. When a Google Drive user requests to download a file, or when the file is downloaded through the sync client, Drive builds a full filename (with extension) based on the name. In cases where the extension is missing, Drive attempts to determine the extension based on the file's MIME type.

Apps should specify a file extension in the
name
property when inserting files with the API. For example, an operation to insert a JPEG file should specify something like
"name": "cat.jpg"
in the metadata.
Subsequent
GET
requests include the read-only
fileExtension
property populated with the extension originally specified in the
name
property. When a Google Drive user requests to download a file, or when the file is downloaded through the sync client, Drive builds a full filename (with extension) based on the name. In cases where the extension is missing, Drive attempts to determine the extension based on the file's MIME type.

Subsequent
GET
requests include the read-only
fileExtension
property populated with the extension originally specified in the
name
property. When a Google Drive user requests to download a file, or when the file is downloaded through the sync client, Drive builds a full filename (with extension) based on the name. In cases where the extension is missing, Drive attempts to determine the extension based on the file's MIME type.


### HTTP request

- Upload URI, for media upload requests:
POST https://www.googleapis.com/upload/drive/v3/files
- Metadata URI, for metadata-only requests:
POST https://www.googleapis.com/drive/v3/files
The URL uses
gRPC Transcoding
syntax.


### Query parameters


| Parameters |  |
| --- | --- |
| enforceSingleParent
(deprecated) | boolean
Deprecated: Creating files in multiple folders is no longer supported. |
| ignoreDefaultVisibility | boolean
Whether to ignore the domain's default visibility settings for the created file. Domain administrators can choose to make all uploaded files visible to the domain by default; this parameter bypasses that behavior for the request. Permissions are still inherited from parent folders. |
| keepRevisionForever | boolean
Whether to set the
keepForever
field in the new head revision. This is only applicable to files with binary content in Google Drive. Only 200 revisions for the file can be kept forever. If the limit is reached, try deleting pinned revisions. |
| ocrLanguage | string
A language hint for OCR processing during image import (ISO 639-1 code). |
| supportsAllDrives | boolean
Whether the requesting application supports both My Drives and shared drives. |
| supportsTeamDrives
(deprecated) | boolean
Deprecated: Use
supportsAllDrives
instead. |
| uploadType | string
The type of upload request to the
/upload
URI. If you are uploading data with an
/upload
URI, this field is required. If you are creating a metadata-only file, this field isn't required. Additionally, this field isn't shown in the "Try this method" widget because the widget doesn't support data uploads.
Acceptable values are:
media
-
Simple upload
. Upload the media only, without any metadata.
multipart
-
Multipart upload
. Upload both the media and its metadata, in a single request.
resumable
-
Resumable upload
. Upload the file in a resumable fashion, using a series of at least two requests where the first request includes the metadata. |
| useContentAsIndexableText | boolean
Whether to use the uploaded content as indexable text. |
| includePermissionsForView | string
Specifies which additional view's permissions to include in the response. Only
published
is supported. |
| includeLabels | string
A comma-separated list of IDs of labels to include in the
labelInfo
part of the response. |

boolean

Deprecated: Creating files in multiple folders is no longer supported.

Whether to ignore the domain's default visibility settings for the created file. Domain administrators can choose to make all uploaded files visible to the domain by default; this parameter bypasses that behavior for the request. Permissions are still inherited from parent folders.

Whether to set the
keepForever
field in the new head revision. This is only applicable to files with binary content in Google Drive. Only 200 revisions for the file can be kept forever. If the limit is reached, try deleting pinned revisions.

string

A language hint for OCR processing during image import (ISO 639-1 code).

Whether the requesting application supports both My Drives and shared drives.

Deprecated: Use
supportsAllDrives
instead.

The type of upload request to the
/upload
URI. If you are uploading data with an
/upload
URI, this field is required. If you are creating a metadata-only file, this field isn't required. Additionally, this field isn't shown in the "Try this method" widget because the widget doesn't support data uploads.

Acceptable values are:

- media
-
Simple upload
. Upload the media only, without any metadata.
- multipart
-
Multipart upload
. Upload both the media and its metadata, in a single request.
- resumable
-
Resumable upload
. Upload the file in a resumable fashion, using a series of at least two requests where the first request includes the metadata.
Whether to use the uploaded content as indexable text.

Specifies which additional view's permissions to include in the response. Only
published
is supported.

A comma-separated list of IDs of labels to include in the
labelInfo
part of the response.


### Request body

The request body contains an instance of
File
.


### Response body

If successful, the response body contains an instance of
File
.


### Authorization scopes

Requires one of the following OAuth scopes:

- https://www.googleapis.com/auth/drive
- https://www.googleapis.com/auth/drive.appdata
- https://www.googleapis.com/auth/drive.file
Some scopes are restricted and require a security assessment for your app to use them. For more information, see the
Authorization guide
.

Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2026-03-20 UTC.


---

# Method: files.delete Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/reference/rest/v3/files/delete

- Home
- Google Workspace
- Google Drive
- Reference
- HTTP request
- Path parameters
- Query parameters
- Request body
- Response body
- Authorization scopes
- Try it!
Permanently deletes a file owned by the user without moving it to the trash. For more information, see
Trash or delete files and folders
.

If the file belongs to a shared drive, the user must be an
organizer
on the parent folder. If the target is a folder, all descendants owned by the user are also deleted.


### HTTP request

DELETE https://www.googleapis.com/drive/v3/files/{fileId}

The URL uses
gRPC Transcoding
syntax.


### Path parameters


| Parameters |  |
| --- | --- |
| fileId | string
The ID of the file. |

string

The ID of the file.


### Query parameters


| Parameters |  |
| --- | --- |
| supportsAllDrives | boolean
Whether the requesting application supports both My Drives and shared drives. |
| supportsTeamDrives
(deprecated) | boolean
Deprecated: Use
supportsAllDrives
instead. |
| enforceSingleParent
(deprecated) | boolean
Deprecated: If an item isn't in a shared drive and its last parent is deleted but the item itself isn't, the item will be placed under its owner's root. |

boolean

Whether the requesting application supports both My Drives and shared drives.

Deprecated: Use
supportsAllDrives
instead.

Deprecated: If an item isn't in a shared drive and its last parent is deleted but the item itself isn't, the item will be placed under its owner's root.


### Request body

The request body must be empty.


### Response body

If successful, the response body is an empty JSON object.


### Authorization scopes

Requires one of the following OAuth scopes:

- https://www.googleapis.com/auth/drive
- https://www.googleapis.com/auth/drive.appdata
- https://www.googleapis.com/auth/drive.file
Some scopes are restricted and require a security assessment for your app to use them. For more information, see the
Authorization guide
.

Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2025-08-26 UTC.


---

# Method: files.download Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/reference/rest/v3/files/download

- Home
- Google Workspace
- Google Drive
- Reference
- HTTP request
- Path parameters
- Query parameters
- Request body
- Response body
- Authorization scopes
- Try it!
Downloads the content of a file. For more information, see
Download and export files
.

Operations are valid for 24 hours from the time of creation.


### HTTP request

POST https://www.googleapis.com/drive/v3/files/{fileId}/download

The URL uses
gRPC Transcoding
syntax.


### Path parameters


| Parameters |  |
| --- | --- |
| fileId | string
Required. The ID of the file to download. |

string

Required. The ID of the file to download.


### Query parameters


| Parameters |  |
| --- | --- |
| mimeType | string
Optional. The MIME type the file should be downloaded as. This field can only be set when downloading Google Workspace documents. For a list of supported MIME types, see
Export MIME types for Google Workspace documents
. If not set, a Google Workspace document is downloaded with a default MIME type. The default MIME type might change in the future. |
| revisionId | string
Optional. The revision ID of the file to download. This field can only be set when downloading blob files, Google Docs, and Google Sheets. Returns
INVALID_ARGUMENT
if downloading a specific revision on the file is unsupported. |

Optional. The MIME type the file should be downloaded as. This field can only be set when downloading Google Workspace documents. For a list of supported MIME types, see
Export MIME types for Google Workspace documents
. If not set, a Google Workspace document is downloaded with a default MIME type. The default MIME type might change in the future.

Optional. The revision ID of the file to download. This field can only be set when downloading blob files, Google Docs, and Google Sheets. Returns
INVALID_ARGUMENT
if downloading a specific revision on the file is unsupported.


### Request body

The request body must be empty.


### Response body

If successful, the response body contains an instance of
Operation
.


### Authorization scopes

Requires one of the following OAuth scopes:

- https://www.googleapis.com/auth/drive
- https://www.googleapis.com/auth/drive.file
- https://www.googleapis.com/auth/drive.readonly
Some scopes are restricted and require a security assessment for your app to use them. For more information, see the
Authorization guide
.

Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2025-08-26 UTC.


---

# Method: files.emptyTrash Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/reference/rest/v3/files/emptyTrash

- Home
- Google Workspace
- Google Drive
- Reference
- HTTP request
- Query parameters
- Request body
- Response body
- Authorization scopes
- Try it!
Permanently deletes all of the user's trashed files. For more information, see
Trash or delete files and folders
.


### HTTP request

DELETE https://www.googleapis.com/drive/v3/files/trash

The URL uses
gRPC Transcoding
syntax.


### Query parameters


| Parameters |  |
| --- | --- |
| enforceSingleParent
(deprecated) | boolean
Deprecated: If an item isn't in a shared drive and its last parent is deleted but the item itself isn't, the item will be placed under its owner's root. |
| driveId | string
If set, empties the trash of the provided shared drive. |

boolean

Deprecated: If an item isn't in a shared drive and its last parent is deleted but the item itself isn't, the item will be placed under its owner's root.

string

If set, empties the trash of the provided shared drive.


### Request body

The request body must be empty.


### Response body

If successful, the response body is an empty JSON object.


### Authorization scopes

Requires the following OAuth scope:

- https://www.googleapis.com/auth/drive
Some scopes are restricted and require a security assessment for your app to use them. For more information, see the
Authorization guide
.

Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2025-08-26 UTC.


---

# Method: files.export Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/reference/rest/v3/files/export

- Home
- Google Workspace
- Google Drive
- Reference
- HTTP request
- Path parameters
- Query parameters
- Request body
- Response body
- Authorization scopes
- Try it!
Exports a Google Workspace document to the requested MIME type and returns exported byte content. For more information, see
Download and export files
.

Note that the exported content is limited to 10 MB.


### HTTP request

GET https://www.googleapis.com/drive/v3/files/{fileId}/export

The URL uses
gRPC Transcoding
syntax.


### Path parameters


| Parameters |  |
| --- | --- |
| fileId | string
The ID of the file. |

string

The ID of the file.


### Query parameters


| Parameters |  |
| --- | --- |
| mimeType | string
Required. The MIME type of the format requested for this export. For a list of supported MIME types, see
Export MIME types for Google Workspace documents
. |

Required. The MIME type of the format requested for this export. For a list of supported MIME types, see
Export MIME types for Google Workspace documents
.


### Request body

The request body must be empty.


### Response body

If successful, this method returns the file content as bytes.


### Authorization scopes

Requires one of the following OAuth scopes:

- https://www.googleapis.com/auth/drive
- https://www.googleapis.com/auth/drive.file
- https://www.googleapis.com/auth/drive.meet.readonly
- https://www.googleapis.com/auth/drive.readonly
Some scopes are restricted and require a security assessment for your app to use them. For more information, see the
Authorization guide
.

Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2025-08-26 UTC.


---

# Method: files.generateCseToken Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/reference/rest/v3/files/generateCseToken

- Home
- Google Workspace
- Google Drive
- Reference
- HTTP request
- Query parameters
- Request body
- Response body
JSON representation
- JSON representation
- Authorization scopes
- Try it!
Generates a CSE token which can be used to create or update CSE files.


### HTTP request

GET https://www.googleapis.com/drive/v3/files/generateCseToken

The URL uses
gRPC Transcoding
syntax.


### Query parameters


| Parameters |  |
| --- | --- |
| fileId | string
The ID of the file for which the JWT should be generated. If not provided, an id will be generated. |
| parent | string
The ID of the expected parent of the file. Used when generating a JWT for a new CSE file. If specified, the parent will be fetched, and if the parent is a shared drive item, the shared drive's policy will be used to determine the KACLS that should be used.
It is invalid to specify both fileId and parent in a single request. |

string

The ID of the file for which the JWT should be generated. If not provided, an id will be generated.

The ID of the expected parent of the file. Used when generating a JWT for a new CSE file. If specified, the parent will be fetched, and if the parent is a shared drive item, the shared drive's policy will be used to determine the KACLS that should be used.

It is invalid to specify both fileId and parent in a single request.


### Request body

The request body must be empty.


### Response body

JWT and associated metadata used to generate CSE files.

If successful, the response body contains data with the following structure:


| JSON representation |
| --- |
| {
"fileId"
:
string
,
"currentKaclsId"
:
string
,
"currentKaclsName"
:
string
,
"jwt"
:
string
,
"kind"
:
string
} |


```json
{
"fileId"
:
string
,
"currentKaclsId"
:
string
,
"currentKaclsName"
:
string
,
"jwt"
:
string
,
"kind"
:
string
}
```


| Fields |  |
| --- | --- |
| fileId | string
The fileId for which the JWT was generated. |
| currentKaclsId | string (
int64
format)
The current Key ACL Service (KACLS) ID associated with the JWT. |
| currentKaclsName | string
Name of the KACLs that the returned KACLs ID points to. |
| jwt | string
The signed JSON Web Token (JWT) for the file. |
| kind | string
Output only. Identifies what kind of resource this is. Value: the fixed string
"drive#generateCseTokenResponse"
. |

The fileId for which the JWT was generated.

string (
int64
format)

The current Key ACL Service (KACLS) ID associated with the JWT.

Name of the KACLs that the returned KACLs ID points to.

The signed JSON Web Token (JWT) for the file.

Output only. Identifies what kind of resource this is. Value: the fixed string
"drive#generateCseTokenResponse"
.


### Authorization scopes

Requires one of the following OAuth scopes:

- https://www.googleapis.com/auth/docs
- https://www.googleapis.com/auth/drive
Some scopes are restricted and require a security assessment for your app to use them. For more information, see the
Authorization guide
.

Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2026-05-01 UTC.


---

# Method: files.generateIds Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/reference/rest/v3/files/generateIds

- Home
- Google Workspace
- Google Drive
- Reference
- HTTP request
- Query parameters
- Request body
- Response body
JSON representation
- JSON representation
- Authorization scopes
- Try it!
Generates a set of file IDs which can be provided in create or copy requests. For more information, see
Create and manage files
.


### HTTP request

GET https://www.googleapis.com/drive/v3/files/generateIds

The URL uses
gRPC Transcoding
syntax.


### Query parameters


| Parameters |  |
| --- | --- |
| count | integer
The number of IDs to return. |
| space | string
The space in which the IDs can be used to create files. Supported values are
drive
and
appDataFolder
. (Default:
drive
.) For more information, see
File organization
. |
| type | string
The type of items which the IDs can be used for. Supported values are
files
and
shortcuts
. Note that
shortcuts
are only supported in the
drive
space
. (Default:
files
.) For more information, see
File organization
. |

integer

The number of IDs to return.

string

The space in which the IDs can be used to create files. Supported values are
drive
and
appDataFolder
. (Default:
drive
.) For more information, see
File organization
.

The type of items which the IDs can be used for. Supported values are
files
and
shortcuts
. Note that
shortcuts
are only supported in the
drive
space
. (Default:
files
.) For more information, see
File organization
.


### Request body

The request body must be empty.


### Response body

A list of generated file IDs which can be provided in create requests.

If successful, the response body contains data with the following structure:


| JSON representation |
| --- |
| {
"ids"
:
[
string
]
,
"space"
:
string
,
"kind"
:
string
} |


```json
{
"ids"
:
[
string
]
,
"space"
:
string
,
"kind"
:
string
}
```


| Fields |  |
| --- | --- |
| ids[] | string
The IDs generated for the requesting user in the specified space. |
| space | string
The type of file that can be created with these IDs. |
| kind | string
Identifies what kind of resource this is. Value: the fixed string
"drive#generatedIds"
. |

The IDs generated for the requesting user in the specified space.

The type of file that can be created with these IDs.

Identifies what kind of resource this is. Value: the fixed string
"drive#generatedIds"
.


### Authorization scopes

Requires one of the following OAuth scopes:

- https://www.googleapis.com/auth/drive
- https://www.googleapis.com/auth/drive.appdata
- https://www.googleapis.com/auth/drive.file
Some scopes are restricted and require a security assessment for your app to use them. For more information, see the
Authorization guide
.

Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2025-08-26 UTC.


---

# Method: files.get Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/reference/rest/v3/files/get

- Home
- Google Workspace
- Google Drive
- Reference
- HTTP request
- Path parameters
- Query parameters
- Request body
- Response body
- Authorization scopes
- Try it!
Gets a file's metadata or content by ID. For more information, see
Search for files and folders
.
If you provide the URL parameter
alt=media
, then the response includes the file contents in the response body. Downloading content with
alt=media
only works if the file is stored in Drive. To download Google Docs, Sheets, and Slides use
files.export
instead. For more information, see
Download and export files
.

If you provide the URL parameter
alt=media
, then the response includes the file contents in the response body. Downloading content with
alt=media
only works if the file is stored in Drive. To download Google Docs, Sheets, and Slides use
files.export
instead. For more information, see
Download and export files
.


### HTTP request

GET https://www.googleapis.com/drive/v3/files/{fileId}

The URL uses
gRPC Transcoding
syntax.


### Path parameters


| Parameters |  |
| --- | --- |
| fileId | string
The ID of the file. |

string

The ID of the file.


### Query parameters


| Parameters |  |
| --- | --- |
| acknowledgeAbuse | boolean
Whether the user is acknowledging the risk of downloading known malware or other abusive files. This is only applicable when the
alt
parameter is set to
media
and the user is the owner of the file or an organizer of the shared drive in which the file resides. |
| supportsAllDrives | boolean
Whether the requesting application supports both My Drives and shared drives. |
| supportsTeamDrives
(deprecated) | boolean
Deprecated: Use
supportsAllDrives
instead. |
| includePermissionsForView | string
Specifies which additional view's permissions to include in the response. Only
published
is supported. |
| includeLabels | string
A comma-separated list of IDs of labels to include in the
labelInfo
part of the response. |

boolean

Whether the user is acknowledging the risk of downloading known malware or other abusive files. This is only applicable when the
alt
parameter is set to
media
and the user is the owner of the file or an organizer of the shared drive in which the file resides.

Whether the requesting application supports both My Drives and shared drives.

Deprecated: Use
supportsAllDrives
instead.

Specifies which additional view's permissions to include in the response. Only
published
is supported.

A comma-separated list of IDs of labels to include in the
labelInfo
part of the response.


### Request body

The request body must be empty.


### Response body

If successful, the response body contains an instance of
File
.


### Authorization scopes

Requires one of the following OAuth scopes:

- https://www.googleapis.com/auth/drive
- https://www.googleapis.com/auth/drive.appdata
- https://www.googleapis.com/auth/drive.file
- https://www.googleapis.com/auth/drive.meet.readonly
- https://www.googleapis.com/auth/drive.metadata
- https://www.googleapis.com/auth/drive.metadata.readonly
- https://www.googleapis.com/auth/drive.photos.readonly
- https://www.googleapis.com/auth/drive.readonly
Some scopes are restricted and require a security assessment for your app to use them. For more information, see the
Authorization guide
.

Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2026-03-20 UTC.


---

# Method: files.list Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/reference/rest/v3/files/list

- Home
- Google Workspace
- Google Drive
- Reference
- HTTP request
- Query parameters
- Request body
- Response body
JSON representation
- JSON representation
- Authorization scopes
- Corpus
- Try it!
Lists the user's files. For more information, see
Search for files and folders
.
This method accepts the
q
parameter, which is a search query combining one or more search terms.
This method returns
all
files by default, including trashed files. If you don't want trashed files to appear in the list, use the
trashed=false
query parameter to remove trashed files from the results.

This method accepts the
q
parameter, which is a search query combining one or more search terms.
This method returns
all
files by default, including trashed files. If you don't want trashed files to appear in the list, use the
trashed=false
query parameter to remove trashed files from the results.

This method returns
all
files by default, including trashed files. If you don't want trashed files to appear in the list, use the
trashed=false
query parameter to remove trashed files from the results.


### HTTP request

GET https://www.googleapis.com/drive/v3/files

The URL uses
gRPC Transcoding
syntax.


### Query parameters


| Parameters |  |
| --- | --- |
| corpora | string
Specifies a collection of items (files or documents) to which the query applies. Supported items include:
user
domain
drive
allDrives
Prefer
user
or
drive
to
allDrives
for efficiency. By default, corpora is set to
user
. However, this can change depending on the filter set through the
q
parameter. For more information, see
File organization
. |
| corpus
(deprecated) | enum (
Corpus
)
Deprecated: The source of files to list. Use
corpora
instead. |
| driveId | string
ID of the shared drive to search. |
| includeItemsFromAllDrives | boolean
Whether both My Drive and shared drive items should be included in results. |
| includeTeamDriveItems
(deprecated) | boolean
Deprecated: Use
includeItemsFromAllDrives
instead. |
| orderBy | string
A comma-separated list of sort keys. Valid keys are:
createdTime
: When the file was created. Avoid using this key for queries on large item collections as it might result in timeouts or other issues. For time-related sorting on large item collections, use
modifiedTime desc
instead.
folder
: The folder ID. This field is sorted using alphabetical ordering.
modifiedByMeTime
: The last time the file was modified by the user.
modifiedTime
: The last time the file was modified by anyone.
name
: The name of the file. This field is sorted using alphabetical ordering, so 1, 12, 2, 22.
name_natural
: The name of the file. This field is sorted using natural sort ordering, so 1, 2, 12, 22.
quotaBytesUsed
: The number of storage quota bytes used by the file.
recency
: The most recent timestamp from the file's date-time fields.
sharedWithMeTime
: When the file was shared with the user, if applicable.
starred
: Whether the user has starred the file.
viewedByMeTime
: The last time the file was viewed by the user.
Each key sorts ascending by default, but can be reversed with the
desc
modifier. Example usage:
?orderBy=folder,modifiedTime desc,name
. |
| pageSize | integer
The maximum number of files to return per page. Pages may be partial or empty even before reaching the end of the file list.
If unspecified, at most 100 files are returned for shared drives, and the entire list of files for non-shared drives.
The maximum value is 100; values above 100 are changed to 100. |
| pageToken | string
The token for continuing a previous list request on the next page. This should be set to the value of
nextPageToken
from the previous response. |
| q | string
A query for filtering the file results. For supported syntax, see
Search for files and folders
. |
| spaces | string
A comma-separated list of spaces to query within the corpora. Supported values are
drive
and
appDataFolder
. For more information, see
File organization
. |
| supportsAllDrives | boolean
Whether the requesting application supports both My Drives and shared drives. |
| supportsTeamDrives
(deprecated) | boolean
Deprecated: Use
supportsAllDrives
instead. |
| teamDriveId
(deprecated) | string
Deprecated: Use
driveId
instead. |
| includePermissionsForView | string
Specifies which additional view's permissions to include in the response. Only
published
is supported. |
| includeLabels | string
A comma-separated list of IDs of labels to include in the
labelInfo
part of the response. |

string

Specifies a collection of items (files or documents) to which the query applies. Supported items include:

- user
- domain
- drive
- allDrives
Prefer
user
or
drive
to
allDrives
for efficiency. By default, corpora is set to
user
. However, this can change depending on the filter set through the
q
parameter. For more information, see
File organization
.

enum (
Corpus
)

Deprecated: The source of files to list. Use
corpora
instead.

ID of the shared drive to search.

boolean

Whether both My Drive and shared drive items should be included in results.

Deprecated: Use
includeItemsFromAllDrives
instead.

A comma-separated list of sort keys. Valid keys are:

- createdTime
: When the file was created. Avoid using this key for queries on large item collections as it might result in timeouts or other issues. For time-related sorting on large item collections, use
modifiedTime desc
instead.
- folder
: The folder ID. This field is sorted using alphabetical ordering.
- modifiedByMeTime
: The last time the file was modified by the user.
- modifiedTime
: The last time the file was modified by anyone.
- name
: The name of the file. This field is sorted using alphabetical ordering, so 1, 12, 2, 22.
- name_natural
: The name of the file. This field is sorted using natural sort ordering, so 1, 2, 12, 22.
- quotaBytesUsed
: The number of storage quota bytes used by the file.
- recency
: The most recent timestamp from the file's date-time fields.
- sharedWithMeTime
: When the file was shared with the user, if applicable.
- starred
: Whether the user has starred the file.
- viewedByMeTime
: The last time the file was viewed by the user.
Each key sorts ascending by default, but can be reversed with the
desc
modifier. Example usage:
?orderBy=folder,modifiedTime desc,name
.

integer

The maximum number of files to return per page. Pages may be partial or empty even before reaching the end of the file list.

If unspecified, at most 100 files are returned for shared drives, and the entire list of files for non-shared drives.

The maximum value is 100; values above 100 are changed to 100.

The token for continuing a previous list request on the next page. This should be set to the value of
nextPageToken
from the previous response.

A query for filtering the file results. For supported syntax, see
Search for files and folders
.

A comma-separated list of spaces to query within the corpora. Supported values are
drive
and
appDataFolder
. For more information, see
File organization
.

Whether the requesting application supports both My Drives and shared drives.

Deprecated: Use
supportsAllDrives
instead.

Deprecated: Use
driveId
instead.

Specifies which additional view's permissions to include in the response. Only
published
is supported.

A comma-separated list of IDs of labels to include in the
labelInfo
part of the response.


### Request body

The request body must be empty.


### Response body

A list of files.

If successful, the response body contains data with the following structure:


| JSON representation |
| --- |
| {
"files"
:
[
{
object (
File
)
}
]
,
"nextPageToken"
:
string
,
"kind"
:
string
,
"incompleteSearch"
:
boolean
} |


```json
{
"files"
:
[
{
object (
File
)
}
]
,
"nextPageToken"
:
string
,
"kind"
:
string
,
"incompleteSearch"
:
boolean
}
```


| Fields |  |
| --- | --- |
| files[] | object (
File
)
The list of files. If
nextPageToken
is populated, then this list may be incomplete and an additional page of results should be fetched. |
| nextPageToken | string
The page token for the next page of files. This will be absent if the end of the files list has been reached. If the token is rejected for any reason, it should be discarded, and pagination should be restarted from the first page of results. The page token is typically valid for several hours. However, if new items are added or removed, your expected results might differ. |
| kind | string
Identifies what kind of resource this is. Value: the fixed string
"drive#fileList"
. |
| incompleteSearch | boolean
Whether the search process was incomplete. If true, then some search results might be missing, since all documents were not searched. This can occur when searching multiple drives with the
allDrives
corpora, but all corpora couldn't be searched. When this happens, it's suggested that clients narrow their query by choosing a different corpus such as
user
or
drive
. |

object (
File
)

The list of files. If
nextPageToken
is populated, then this list may be incomplete and an additional page of results should be fetched.

The page token for the next page of files. This will be absent if the end of the files list has been reached. If the token is rejected for any reason, it should be discarded, and pagination should be restarted from the first page of results. The page token is typically valid for several hours. However, if new items are added or removed, your expected results might differ.

Identifies what kind of resource this is. Value: the fixed string
"drive#fileList"
.

Whether the search process was incomplete. If true, then some search results might be missing, since all documents were not searched. This can occur when searching multiple drives with the
allDrives
corpora, but all corpora couldn't be searched. When this happens, it's suggested that clients narrow their query by choosing a different corpus such as
user
or
drive
.


### Authorization scopes

Requires one of the following OAuth scopes:

- https://www.googleapis.com/auth/drive
- https://www.googleapis.com/auth/drive.appdata
- https://www.googleapis.com/auth/drive.file
- https://www.googleapis.com/auth/drive.meet.readonly
- https://www.googleapis.com/auth/drive.metadata
- https://www.googleapis.com/auth/drive.metadata.readonly
- https://www.googleapis.com/auth/drive.photos.readonly
- https://www.googleapis.com/auth/drive.readonly
Some scopes are restricted and require a security assessment for your app to use them. For more information, see the
Authorization guide
.


## Corpus


| Enums |  |
| --- | --- |
| user | Files owned by or shared to the user. |
| domain | Files shared to the user's domain. |

Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2026-04-24 UTC.


---

# Method: files.listLabels Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/reference/rest/v3/files/listLabels

- Home
- Google Workspace
- Google Drive
- Reference
- HTTP request
- Path parameters
- Query parameters
- Request body
- Response body
JSON representation
- JSON representation
- Authorization scopes
- Try it!
Lists the labels on a file. For more information, see
List labels on a file
.


### HTTP request

GET https://www.googleapis.com/drive/v3/files/{fileId}/listLabels

The URL uses
gRPC Transcoding
syntax.


### Path parameters


| Parameters |  |
| --- | --- |
| fileId | string
The ID for the file. |

string

The ID for the file.


### Query parameters


| Parameters |  |
| --- | --- |
| maxResults | integer
The maximum number of labels to return per page. When not set, defaults to 100. |
| pageToken | string
The token for continuing a previous list request on the next page. This should be set to the value of
nextPageToken
from the previous response. |

integer

The maximum number of labels to return per page. When not set, defaults to 100.

The token for continuing a previous list request on the next page. This should be set to the value of
nextPageToken
from the previous response.


### Request body

The request body must be empty.


### Response body

A list of labels applied to a file.

If successful, the response body contains data with the following structure:


| JSON representation |
| --- |
| {
"labels"
:
[
{
object (
Label
)
}
]
,
"nextPageToken"
:
string
,
"kind"
:
string
} |


```json
{
"labels"
:
[
{
object (
Label
)
}
]
,
"nextPageToken"
:
string
,
"kind"
:
string
}
```


| Fields |  |
| --- | --- |
| labels[] | object (
Label
)
The list of labels. |
| nextPageToken | string
The page token for the next page of labels. This field will be absent if the end of the list has been reached. If the token is rejected for any reason, it should be discarded, and pagination should be restarted from the first page of results. The page token is typically valid for several hours. However, if new items are added or removed, your expected results might differ. |
| kind | string
This is always
"drive#labelList"
. |

object (
Label
)

The list of labels.

The page token for the next page of labels. This field will be absent if the end of the list has been reached. If the token is rejected for any reason, it should be discarded, and pagination should be restarted from the first page of results. The page token is typically valid for several hours. However, if new items are added or removed, your expected results might differ.

This is always
"drive#labelList"
.


### Authorization scopes

Requires one of the following OAuth scopes:

- https://www.googleapis.com/auth/drive
- https://www.googleapis.com/auth/drive.file
- https://www.googleapis.com/auth/drive.meet.readonly
- https://www.googleapis.com/auth/drive.metadata
- https://www.googleapis.com/auth/drive.metadata.readonly
- https://www.googleapis.com/auth/drive.readonly
Some scopes are restricted and require a security assessment for your app to use them. For more information, see the
Authorization guide
.

Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2025-08-26 UTC.


---

# Method: files.modifyLabels Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/reference/rest/v3/files/modifyLabels

- Home
- Google Workspace
- Google Drive
- Reference
- HTTP request
- Path parameters
- Request body
- Response body
JSON representation
- JSON representation
- Authorization scopes
- ModifyLabelsRequest
JSON representation
- LabelModification
JSON representation
- FieldModification
JSON representation
- Try it!
Modifies the set of labels applied to a file. For more information, see
Set a label field on a file
.

Returns a list of the labels that were added or modified.


### HTTP request

POST https://www.googleapis.com/drive/v3/files/{fileId}/modifyLabels

The URL uses
gRPC Transcoding
syntax.


### Path parameters


| Parameters |  |
| --- | --- |
| fileId | string
The ID of the file to which the labels belong. |

string

The ID of the file to which the labels belong.


### Request body

The request body contains an instance of
ModifyLabelsRequest
.


### Response body

Response to a
files.modifyLabels
request. This contains only those labels which were added or updated by the request.

If successful, the response body contains data with the following structure:


| JSON representation |
| --- |
| {
"modifiedLabels"
:
[
{
object (
Label
)
}
]
,
"kind"
:
string
} |


```json
{
"modifiedLabels"
:
[
{
object (
Label
)
}
]
,
"kind"
:
string
}
```


| Fields |  |
| --- | --- |
| modifiedLabels[] | object (
Label
)
The list of labels which were added or updated by the request. |
| kind | string
This is always
"drive#modifyLabelsResponse"
. |

object (
Label
)

The list of labels which were added or updated by the request.

This is always
"drive#modifyLabelsResponse"
.


### Authorization scopes

Requires one of the following OAuth scopes:

- https://www.googleapis.com/auth/drive
- https://www.googleapis.com/auth/drive.file
- https://www.googleapis.com/auth/drive.metadata
Some scopes are restricted and require a security assessment for your app to use them. For more information, see the
Authorization guide
.


## ModifyLabelsRequest

A request to modify the set of labels on a file. This request may contain many modifications that will either all succeed or all fail atomically.


| JSON representation |
| --- |
| {
"labelModifications"
:
[
{
object (
LabelModification
)
}
]
,
"kind"
:
string
} |


```json
{
"labelModifications"
:
[
{
object (
LabelModification
)
}
]
,
"kind"
:
string
}
```


| Fields |  |
| --- | --- |
| labelModifications[] | object (
LabelModification
)
The list of modifications to apply to the labels on the file. |
| kind | string
This is always
"drive#modifyLabelsRequest"
. |

object (
LabelModification
)

The list of modifications to apply to the labels on the file.

This is always
"drive#modifyLabelsRequest"
.


## LabelModification

A modification to a label on a file. A
LabelModification
can be used to apply a label to a file, update an existing label on a file, or remove a label from a file.


| JSON representation |
| --- |
| {
"fieldModifications"
:
[
{
object (
FieldModification
)
}
]
,
"labelId"
:
string
,
"removeLabel"
:
boolean
,
"kind"
:
string
} |


```json
{
"fieldModifications"
:
[
{
object (
FieldModification
)
}
]
,
"labelId"
:
string
,
"removeLabel"
:
boolean
,
"kind"
:
string
}
```


| Fields |  |
| --- | --- |
| fieldModifications[] | object (
FieldModification
)
The list of modifications to this label's fields. |
| labelId | string
The ID of the label to modify. |
| removeLabel | boolean
If true, the label will be removed from the file. |
| kind | string
This is always
"drive#labelModification"
. |

object (
FieldModification
)

The list of modifications to this label's fields.

The ID of the label to modify.

boolean

If true, the label will be removed from the file.

This is always
"drive#labelModification"
.


## FieldModification

A modification to a label's field.


| JSON representation |
| --- |
| {
"setDateValues"
:
[
string
]
,
"setTextValues"
:
[
string
]
,
"setSelectionValues"
:
[
string
]
,
"setIntegerValues"
:
[
string
]
,
"setUserValues"
:
[
string
]
,
"fieldId"
:
string
,
"kind"
:
string
,
"unsetValues"
:
boolean
} |


```json
{
"setDateValues"
:
[
string
]
,
"setTextValues"
:
[
string
]
,
"setSelectionValues"
:
[
string
]
,
"setIntegerValues"
:
[
string
]
,
"setUserValues"
:
[
string
]
,
"fieldId"
:
string
,
"kind"
:
string
,
"unsetValues"
:
boolean
}
```


| Fields |  |
| --- | --- |
| setDateValues[] | string
Replaces the value of a
date
field with these new values. The string must be in the RFC 3339 full-date format: YYYY-MM-DD. |
| setTextValues[] | string
Sets the value of a
text
field. |
| setSelectionValues[] | string
Replaces a
selection
field with these new values. |
| setIntegerValues[] | string (
int64
format)
Replaces the value of an
integer
field with these new values. |
| setUserValues[] | string
Replaces a
user
field with these new values. The values must be a valid email addresses. |
| fieldId | string
The ID of the field to be modified. |
| kind | string
This is always
"drive#labelFieldModification"
. |
| unsetValues | boolean
Unsets the values for this field. |

Replaces the value of a
date
field with these new values. The string must be in the RFC 3339 full-date format: YYYY-MM-DD.

Sets the value of a
text
field.

Replaces a
selection
field with these new values.

string (
int64
format)

Replaces the value of an
integer
field with these new values.

Replaces a
user
field with these new values. The values must be a valid email addresses.

The ID of the field to be modified.

This is always
"drive#labelFieldModification"
.

Unsets the values for this field.

Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2025-08-26 UTC.


---

# Method: files.update Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/reference/rest/v3/files/update

- Home
- Google Workspace
- Google Drive
- Reference
- HTTP request
- Path parameters
- Query parameters
- Request body
- Response body
- Authorization scopes
- Try it!
Updates a file's metadata, content, or both.
When calling this method, only populate fields in the request that you want to modify. When updating fields, some fields might be changed automatically, such as
modifiedDate
. This method supports patch semantics.
This method supports an
/upload
URI and accepts uploaded media with the following characteristics:
Maximum file size:
5,120 GB
Accepted Media MIME types:
*/*
(Specify a valid MIME type, rather than the literal
*/*
value. The literal
*/*
is only used to indicate that any valid MIME type can be uploaded. For more information, see
Google Workspace and Google Drive supported MIME types
.)
For more information on uploading files, see
Upload file data
.

When calling this method, only populate fields in the request that you want to modify. When updating fields, some fields might be changed automatically, such as
modifiedDate
. This method supports patch semantics.
This method supports an
/upload
URI and accepts uploaded media with the following characteristics:
Maximum file size:
5,120 GB
Accepted Media MIME types:
*/*
(Specify a valid MIME type, rather than the literal
*/*
value. The literal
*/*
is only used to indicate that any valid MIME type can be uploaded. For more information, see
Google Workspace and Google Drive supported MIME types
.)
For more information on uploading files, see
Upload file data
.

This method supports an
/upload
URI and accepts uploaded media with the following characteristics:
Maximum file size:
5,120 GB
Accepted Media MIME types:
*/*
(Specify a valid MIME type, rather than the literal
*/*
value. The literal
*/*
is only used to indicate that any valid MIME type can be uploaded. For more information, see
Google Workspace and Google Drive supported MIME types
.)
For more information on uploading files, see
Upload file data
.

- Maximum file size:
5,120 GB
- Accepted Media MIME types:
*/*
(Specify a valid MIME type, rather than the literal
*/*
value. The literal
*/*
is only used to indicate that any valid MIME type can be uploaded. For more information, see
Google Workspace and Google Drive supported MIME types
.)
(Specify a valid MIME type, rather than the literal
*/*
value. The literal
*/*
is only used to indicate that any valid MIME type can be uploaded. For more information, see
Google Workspace and Google Drive supported MIME types
.)

For more information on uploading files, see
Upload file data
.


### HTTP request

- Upload URI, for media upload requests:
PATCH https://www.googleapis.com/upload/drive/v3/files/{fileId}
- Metadata URI, for metadata-only requests:
PATCH https://www.googleapis.com/drive/v3/files/{fileId}
The URL uses
gRPC Transcoding
syntax.


### Path parameters


| Parameters |  |
| --- | --- |
| fileId | string
The ID of the file. |

string

The ID of the file.


### Query parameters


| Parameters |  |
| --- | --- |
| addParents | string
A comma-separated list of parent IDs to add. |
| enforceSingleParent
(deprecated) | boolean
Deprecated: Adding files to multiple folders is no longer supported. Use shortcuts instead. |
| keepRevisionForever | boolean
Whether to set the
keepForever
field in the new head revision. This is only applicable to files with binary content in Google Drive. Only 200 revisions for the file can be kept forever. If the limit is reached, try deleting pinned revisions. |
| ocrLanguage | string
A language hint for OCR processing during image import (ISO 639-1 code). |
| removeParents | string
A comma-separated list of parent IDs to remove. |
| supportsAllDrives | boolean
Whether the requesting application supports both My Drives and shared drives. |
| supportsTeamDrives
(deprecated) | boolean
Deprecated: Use
supportsAllDrives
instead. |
| uploadType | string
The type of upload request to the
/upload
URI. If you are uploading data with an
/upload
URI, this field is required. If you are creating a metadata-only file, this field isn't required. Additionally, this field isn't shown in the "Try this method" widget because the widget doesn't support data uploads.
Acceptable values are:
media
-
Simple upload
. Upload the media only, without any metadata.
multipart
-
Multipart upload
. Upload both the media and its metadata, in a single request.
resumable
-
Resumable upload
. Upload the file in a resumable fashion, using a series of at least two requests where the first request includes the metadata. |
| useContentAsIndexableText | boolean
Whether to use the uploaded content as indexable text. |
| includePermissionsForView | string
Specifies which additional view's permissions to include in the response. Only
published
is supported. |
| includeLabels | string
A comma-separated list of IDs of labels to include in the
labelInfo
part of the response. |

A comma-separated list of parent IDs to add.

boolean

Deprecated: Adding files to multiple folders is no longer supported. Use shortcuts instead.

Whether to set the
keepForever
field in the new head revision. This is only applicable to files with binary content in Google Drive. Only 200 revisions for the file can be kept forever. If the limit is reached, try deleting pinned revisions.

A language hint for OCR processing during image import (ISO 639-1 code).

A comma-separated list of parent IDs to remove.

Whether the requesting application supports both My Drives and shared drives.

Deprecated: Use
supportsAllDrives
instead.

The type of upload request to the
/upload
URI. If you are uploading data with an
/upload
URI, this field is required. If you are creating a metadata-only file, this field isn't required. Additionally, this field isn't shown in the "Try this method" widget because the widget doesn't support data uploads.

Acceptable values are:

- media
-
Simple upload
. Upload the media only, without any metadata.
- multipart
-
Multipart upload
. Upload both the media and its metadata, in a single request.
- resumable
-
Resumable upload
. Upload the file in a resumable fashion, using a series of at least two requests where the first request includes the metadata.
Whether to use the uploaded content as indexable text.

Specifies which additional view's permissions to include in the response. Only
published
is supported.

A comma-separated list of IDs of labels to include in the
labelInfo
part of the response.


### Request body

The request body contains an instance of
File
.


### Response body

If successful, the response body contains an instance of
File
.


### Authorization scopes

Requires one of the following OAuth scopes:

- https://www.googleapis.com/auth/drive
- https://www.googleapis.com/auth/drive.appdata
- https://www.googleapis.com/auth/drive.file
- https://www.googleapis.com/auth/drive.metadata
- https://www.googleapis.com/auth/drive.scripts
Some scopes are restricted and require a security assessment for your app to use them. For more information, see the
Authorization guide
.

Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2026-03-20 UTC.


---

# Method: files.watch Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/reference/rest/v3/files/watch

- Home
- Google Workspace
- Google Drive
- Reference
- HTTP request
- Path parameters
- Query parameters
- Request body
- Response body
- Authorization scopes
Subscribes to changes to a file. For more information, see
Notifications for resource changes
.


### HTTP request

POST https://www.googleapis.com/drive/v3/files/{fileId}/watch

The URL uses
gRPC Transcoding
syntax.


### Path parameters


| Parameters |  |
| --- | --- |
| fileId | string
The ID of the file. |

string

The ID of the file.


### Query parameters


| Parameters |  |
| --- | --- |
| supportsAllDrives | boolean
Whether the requesting application supports both My Drives and shared drives. |
| supportsTeamDrives
(deprecated) | boolean
Deprecated: Use
supportsAllDrives
instead. |
| acknowledgeAbuse | boolean
Whether the user is acknowledging the risk of downloading known malware or other abusive files. This is only applicable when the
alt
parameter is set to
media
and the user is the owner of the file or an organizer of the shared drive in which the file resides. |
| includePermissionsForView | string
Specifies which additional view's permissions to include in the response. Only
published
is supported. |
| includeLabels | string
A comma-separated list of IDs of labels to include in the
labelInfo
part of the response. |

boolean

Whether the requesting application supports both My Drives and shared drives.

Deprecated: Use
supportsAllDrives
instead.

Whether the user is acknowledging the risk of downloading known malware or other abusive files. This is only applicable when the
alt
parameter is set to
media
and the user is the owner of the file or an organizer of the shared drive in which the file resides.

Specifies which additional view's permissions to include in the response. Only
published
is supported.

A comma-separated list of IDs of labels to include in the
labelInfo
part of the response.


### Request body

The request body contains an instance of
Channel
.


### Response body

If successful, the response body contains an instance of
Channel
.


### Authorization scopes

Requires one of the following OAuth scopes:

- https://www.googleapis.com/auth/drive
- https://www.googleapis.com/auth/drive.appdata
- https://www.googleapis.com/auth/drive.file
- https://www.googleapis.com/auth/drive.meet.readonly
- https://www.googleapis.com/auth/drive.metadata
- https://www.googleapis.com/auth/drive.metadata.readonly
- https://www.googleapis.com/auth/drive.photos.readonly
- https://www.googleapis.com/auth/drive.readonly
Some scopes are restricted and require a security assessment for your app to use them. For more information, see the
Authorization guide
.

Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2025-08-26 UTC.


---

# REST Resource: operations Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/reference/rest/v3/operations

- Home
- Google Workspace
- Google Drive
- Reference
- Resource: Operation
JSON representation
- JSON representation
- Status
JSON representation
- Methods

## Resource: Operation

This resource represents a long-running operation that is the result of a network API call.


| JSON representation |
| --- |
| {
"name"
:
string
,
"metadata"
:
{
"@type"
:
string
,
field1
:
...
,
...
}
,
"done"
:
boolean
,
"error"
:
{
object (
Status
)
}
,
"response"
:
{
"@type"
:
string
,
field1
:
...
,
...
}
} |


```json
{
"name"
:
string
,
"metadata"
:
{
"@type"
:
string
,
field1
:
...
,
...
}
,
"done"
:
boolean
,
"error"
:
{
object (
Status
)
}
,
"response"
:
{
"@type"
:
string
,
field1
:
...
,
...
}
}
```


| Fields |  |
| --- | --- |
| name | string
The server-assigned name, which is only unique within the same service that originally returns it. If you use the default HTTP mapping, the
name
should be a resource name ending with
operations/{unique_id}
. |
| metadata | object
Service-specific metadata associated with the operation. It typically contains progress information and common metadata such as create time. Some services might not provide such metadata. Any method that returns a long-running operation should document the metadata type, if any.
An object containing fields of an arbitrary type. An additional field
"@type"
contains a URI identifying the type. Example:
{ "id": 1234, "@type": "types.example.com/standard/id" }
. |
| done | boolean
If the value is
false
, it means the operation is still in progress. If
true
, the operation is completed, and either
error
or
response
is available. |
| Union field
result
. The operation result, which can be either an
error
or a valid
response
. If
done
==
false
, neither
error
nor
response
is set. If
done
==
true
, exactly one of
error
or
response
can be set. Some services might not provide the result.
result
can be only one of the following: |  |
| error | object (
Status
)
The error result of the operation in case of failure or cancellation. |
| response | object
The normal, successful response of the operation. If the original method returns no data on success, such as
Delete
, the response is
google.protobuf.Empty
. If the original method is standard
Get
/
Create
/
Update
, the response should be the resource. For other methods, the response should have the type
XxxResponse
, where
Xxx
is the original method name. For example, if the original method name is
TakeSnapshot()
, the inferred response type is
TakeSnapshotResponse
.
An object containing fields of an arbitrary type. An additional field
"@type"
contains a URI identifying the type. Example:
{ "id": 1234, "@type": "types.example.com/standard/id" }
. |

string

The server-assigned name, which is only unique within the same service that originally returns it. If you use the default HTTP mapping, the
name
should be a resource name ending with
operations/{unique_id}
.

object

Service-specific metadata associated with the operation. It typically contains progress information and common metadata such as create time. Some services might not provide such metadata. Any method that returns a long-running operation should document the metadata type, if any.

An object containing fields of an arbitrary type. An additional field
"@type"
contains a URI identifying the type. Example:
{ "id": 1234, "@type": "types.example.com/standard/id" }
.

boolean

If the value is
false
, it means the operation is still in progress. If
true
, the operation is completed, and either
error
or
response
is available.

object (
Status
)

The error result of the operation in case of failure or cancellation.

The normal, successful response of the operation. If the original method returns no data on success, such as
Delete
, the response is
google.protobuf.Empty
. If the original method is standard
Get
/
Create
/
Update
, the response should be the resource. For other methods, the response should have the type
XxxResponse
, where
Xxx
is the original method name. For example, if the original method name is
TakeSnapshot()
, the inferred response type is
TakeSnapshotResponse
.


## Status

The
Status
type defines a logical error model that is suitable for different programming environments, including REST APIs and RPC APIs. It is used by
gRPC
. Each
Status
message contains three pieces of data: error code, error message, and error details.

You can find out more about this error model and how to work with it in the
API Design Guide
.


| JSON representation |
| --- |
| {
"code"
:
integer
,
"message"
:
string
,
"details"
:
[
{
"@type"
:
string
,
field1
:
...
,
...
}
]
} |


```json
{
"code"
:
integer
,
"message"
:
string
,
"details"
:
[
{
"@type"
:
string
,
field1
:
...
,
...
}
]
}
```


| Fields |  |
| --- | --- |
| code | integer
The status code, which should be an enum value of
google.rpc.Code
. |
| message | string
A developer-facing error message, which should be in English. Any user-facing error message should be localized and sent in the
google.rpc.Status.details
field, or localized by the client. |
| details[] | object
A list of messages that carry the error details. There is a common set of message types for APIs to use.
An object containing fields of an arbitrary type. An additional field
"@type"
contains a URI identifying the type. Example:
{ "id": 1234, "@type": "types.example.com/standard/id" }
. |

integer

The status code, which should be an enum value of
google.rpc.Code
.

A developer-facing error message, which should be in English. Any user-facing error message should be localized and sent in the
google.rpc.Status.details
field, or localized by the client.

A list of messages that carry the error details. There is a common set of message types for APIs to use.


| Methods |  |
| --- | --- |
| get | Gets the latest state of a long-running operation. |


## Methods


### get

Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2026-03-20 UTC.


---

# Method: operations.get Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/reference/rest/v3/operations/get

- Home
- Google Workspace
- Google Drive
- Reference
- HTTP request
- Path parameters
- Request body
- Response body
- Authorization scopes
- Try it!
Gets the latest state of a long-running operation. Clients can use this method to poll the operation result at intervals as recommended by the API service.


### HTTP request

GET https://www.googleapis.com/drive/v3/operations/{name}

The URL uses
gRPC Transcoding
syntax.


### Path parameters


| Parameters |  |
| --- | --- |
| name | string
The name of the operation resource. |

string

The name of the operation resource.


### Request body

The request body must be empty.


### Response body

If successful, the response body contains an instance of
Operation
.


### Authorization scopes

Requires one of the following OAuth scopes:

- https://www.googleapis.com/auth/drive
- https://www.googleapis.com/auth/drive.file
- https://www.googleapis.com/auth/drive.meet.readonly
- https://www.googleapis.com/auth/drive.readonly
Some scopes are restricted and require a security assessment for your app to use them. For more information, see the
Authorization guide
.

Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2025-04-18 UTC.


---

# REST Resource: permissions Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/reference/rest/v3/permissions

- Home
- Google Workspace
- Google Drive
- Reference
- Resource: Permission
JSON representation
- JSON representation
- Methods

## Resource: Permission

A permission for a file. A permission grants a user, group, domain, or the world access to a file or a folder hierarchy. For more information, see
Share files, folders, and drives
.

By default, permission requests only return a subset of fields. Permission
kind
,
ID
,
type
, and
role
are always returned. To retrieve specific fields, see
Return specific fields
.

Some resource methods (such as
permissions.update
) require a
permissionId
. Use the
permissions.list
method to retrieve the ID for a file, folder, or shared drive.


| JSON representation |
| --- |
| {
"id"
:
string
,
"displayName"
:
string
,
"type"
:
string
,
"kind"
:
string
,
"permissionDetails"
:
[
{
"permissionType"
:
string
,
"inheritedFrom"
:
string
,
"role"
:
string
,
"inherited"
:
boolean
}
]
,
"photoLink"
:
string
,
"emailAddress"
:
string
,
"role"
:
string
,
"allowFileDiscovery"
:
boolean
,
"domain"
:
string
,
"expirationTime"
:
string
,
"teamDrivePermissionDetails"
:
[
{
"teamDrivePermissionType"
:
string
,
"inheritedFrom"
:
string
,
"role"
:
string
,
"inherited"
:
boolean
}
]
,
"deleted"
:
boolean
,
"view"
:
string
,
"pendingOwner"
:
boolean
,
"inheritedPermissionsDisabled"
:
boolean
} |


```json
{
"id"
:
string
,
"displayName"
:
string
,
"type"
:
string
,
"kind"
:
string
,
"permissionDetails"
:
[
{
"permissionType"
:
string
,
"inheritedFrom"
:
string
,
"role"
:
string
,
"inherited"
:
boolean
}
]
,
"photoLink"
:
string
,
"emailAddress"
:
string
,
"role"
:
string
,
"allowFileDiscovery"
:
boolean
,
"domain"
:
string
,
"expirationTime"
:
string
,
"teamDrivePermissionDetails"
:
[
{
"teamDrivePermissionType"
:
string
,
"inheritedFrom"
:
string
,
"role"
:
string
,
"inherited"
:
boolean
}
]
,
"deleted"
:
boolean
,
"view"
:
string
,
"pendingOwner"
:
boolean
,
"inheritedPermissionsDisabled"
:
boolean
}
```


| Fields |  |
| --- | --- |
| id | string
Output only. The ID of this permission. This is a unique identifier for the grantee, and is published in the
User resource
as
permissionId
. IDs should be treated as opaque values. |
| displayName | string
Output only. The "pretty" name of the value of the permission. The following is a list of examples for each type of permission:
user
- User's full name, as defined for their Google Account, such as "Dana A."
group
- Name of the Google Group, such as "The Company Administrators."
domain
- String domain name, such as "cymbalgroup.com."
anyone
- No
displayName
is present. |
| type | string
The type of the grantee. Supported values include:
user
group
domain
anyone
When creating a permission, if
type
is
user
or
group
, you must provide an
emailAddress
for the user or group. If
type
is
domain
, you must provide a
domain
. If
type
is
anyone
, no extra information is required. |
| kind | string
Output only. Identifies what kind of resource this is. Value: the fixed string
"drive#permission"
. |
| permissionDetails[] | object
Output only. Details of whether the permissions on this item are inherited or are directly on this item. |
| permissionDetails[].permissionType | string
Output only. The permission type for this user. Supported values include:
file
member |
| permissionDetails[].inheritedFrom | string
Output only. The ID of the item from which this permission is inherited. This is only populated for items in shared drives. |
| permissionDetails[].role | string
Output only. The primary role for this user. Supported values include:
owner
organizer
fileOrganizer
writer
commenter
reader
For more information, see
Roles and permissions
. |
| permissionDetails[].inherited | boolean
Output only. Whether this permission is inherited. This field is always populated. This is an output-only field. |
| photoLink | string
Output only. A link to the user's profile photo, if available. |
| emailAddress | string
Output only. The email address of the user or group to which this permission refers. |
| role | string
The role granted by this permission. Supported values include:
owner
organizer
fileOrganizer
writer
commenter
reader
For more information, see
Roles and permissions
. |
| allowFileDiscovery | boolean
Whether the permission allows the file to be discovered through search. This is only applicable for permissions of type
domain
or
anyone
. |
| domain | string
Output only. The domain to which this permission refers. |
| expirationTime | string
The time at which this permission will expire (
RFC 3339 date-time
). Expiration times have the following restrictions:
They can only be set on user and group permissions.
The time must be in the future.
The time cannot be more than one year in the future. |
| teamDrivePermissionDetails[]
(deprecated) | object
Output only. Deprecated: Output only. Use
permissionDetails
instead. |
| teamDrivePermissionDetails[]
(deprecated)
.teamDrivePermissionType
(deprecated) | string
Deprecated: Output only. Use
permissionDetails/permissionType
instead. |
| teamDrivePermissionDetails[]
(deprecated)
.inheritedFrom
(deprecated) | string
Deprecated: Output only. Use
permissionDetails/inheritedFrom
instead. |
| teamDrivePermissionDetails[]
(deprecated)
.role
(deprecated) | string
Deprecated: Output only. Use
permissionDetails/role
instead. |
| teamDrivePermissionDetails[]
(deprecated)
.inherited
(deprecated) | boolean
Deprecated: Output only. Use
permissionDetails/inherited
instead. |
| deleted | boolean
Output only. Whether the account associated with this permission has been deleted. This field only pertains to permissions of type
user
or
group
. |
| view | string
Indicates the view for this permission. Only populated for permissions that belong to a view.
The only supported values are
published
and
metadata
:
published
: The permission's role is
publishedReader
.
metadata
: The item is only visible to the
metadata
view because the item has limited access and the scope has at least read access to the parent. The
metadata
view is only supported on folders.
For more information, see
Views
. |
| pendingOwner | boolean
Whether the account associated with this permission is a pending owner. Only populated for permissions of type
user
for files that aren't in a shared drive. |
| inheritedPermissionsDisabled | boolean
When
true
, only organizers, owners, and users with permissions added directly on the item can access it. |

string

Output only. The ID of this permission. This is a unique identifier for the grantee, and is published in the
User resource
as
permissionId
. IDs should be treated as opaque values.

Output only. The "pretty" name of the value of the permission. The following is a list of examples for each type of permission:

- user
- User's full name, as defined for their Google Account, such as "Dana A."
- group
- Name of the Google Group, such as "The Company Administrators."
- domain
- String domain name, such as "cymbalgroup.com."
- anyone
- No
displayName
is present.
The type of the grantee. Supported values include:

- user
- group
- domain
- anyone
When creating a permission, if
type
is
user
or
group
, you must provide an
emailAddress
for the user or group. If
type
is
domain
, you must provide a
domain
. If
type
is
anyone
, no extra information is required.

Output only. Identifies what kind of resource this is. Value: the fixed string
"drive#permission"
.

object

Output only. Details of whether the permissions on this item are inherited or are directly on this item.

Output only. The permission type for this user. Supported values include:

- file
- member
Output only. The ID of the item from which this permission is inherited. This is only populated for items in shared drives.

Output only. The primary role for this user. Supported values include:

- owner
- organizer
- fileOrganizer
- writer
- commenter
- reader
For more information, see
Roles and permissions
.

boolean

Output only. Whether this permission is inherited. This field is always populated. This is an output-only field.

Output only. A link to the user's profile photo, if available.

Output only. The email address of the user or group to which this permission refers.

The role granted by this permission. Supported values include:

Whether the permission allows the file to be discovered through search. This is only applicable for permissions of type
domain
or
anyone
.

Output only. The domain to which this permission refers.

The time at which this permission will expire (
RFC 3339 date-time
). Expiration times have the following restrictions:

- They can only be set on user and group permissions.
- The time must be in the future.
- The time cannot be more than one year in the future.
Output only. Deprecated: Output only. Use
permissionDetails
instead.

Deprecated: Output only. Use
permissionDetails/permissionType
instead.

Deprecated: Output only. Use
permissionDetails/inheritedFrom
instead.

Deprecated: Output only. Use
permissionDetails/role
instead.

Deprecated: Output only. Use
permissionDetails/inherited
instead.

Output only. Whether the account associated with this permission has been deleted. This field only pertains to permissions of type
user
or
group
.

Indicates the view for this permission. Only populated for permissions that belong to a view.

The only supported values are
published
and
metadata
:

- published
: The permission's role is
publishedReader
.
- metadata
: The item is only visible to the
metadata
view because the item has limited access and the scope has at least read access to the parent. The
metadata
view is only supported on folders.
For more information, see
Views
.

Whether the account associated with this permission is a pending owner. Only populated for permissions of type
user
for files that aren't in a shared drive.

When
true
, only organizers, owners, and users with permissions added directly on the item can access it.


| Methods |  |
| --- | --- |
| create | Creates a permission for a file or shared drive. |
| delete | Deletes a permission. |
| get | Gets a permission by ID. |
| list | Lists a file's or shared drive's permissions. |
| update | Updates a permission with patch semantics. |


## Methods


### create


### delete


### get


### list


### update

Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2026-04-21 UTC.


---

# Method: permissions.create Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/reference/rest/v3/permissions/create

- Home
- Google Workspace
- Google Drive
- Reference
- HTTP request
- Path parameters
- Query parameters
- Request body
- Response body
- Authorization scopes
- Try it!
Creates a permission for a file or shared drive. For more information, see
Share files, folders, and drives
.

Warning:
Concurrent permissions operations on the same file aren't supported; only the last update is applied.


### HTTP request

POST https://www.googleapis.com/drive/v3/files/{fileId}/permissions

The URL uses
gRPC Transcoding
syntax.


### Path parameters


| Parameters |  |
| --- | --- |
| fileId | string
The ID of the file or shared drive. |

string

The ID of the file or shared drive.


### Query parameters


| Parameters |  |
| --- | --- |
| emailMessage | string
A plain text custom message to include in the notification email. |
| enforceSingleParent
(deprecated) | boolean
Deprecated: See
moveToNewOwnersRoot
for details. |
| moveToNewOwnersRoot | boolean
This parameter only takes effect if the item isn't in a shared drive and the request is attempting to transfer the ownership of the item. If set to
true
, the item is moved to the new owner's My Drive root folder and all prior parents removed. If set to
false
, parents aren't changed. |
| sendNotificationEmail | boolean
Whether to send a notification email when sharing to users or groups. This defaults to
true
for users and groups, and is not allowed for other requests. It must not be disabled for ownership transfers. |
| supportsAllDrives | boolean
Whether the requesting application supports both My Drives and shared drives. |
| supportsTeamDrives
(deprecated) | boolean
Deprecated: Use
supportsAllDrives
instead. |
| transferOwnership | boolean
Whether to transfer ownership to the specified user and downgrade the current owner to a writer. This parameter is required as an acknowledgement of the side effect. For more information, see
Transfer file ownership
. |
| useDomainAdminAccess | boolean
Issue the request as a domain administrator.
If set to
true
, and if the following additional conditions are met, the requester is granted access:
The file ID parameter refers to a shared drive.
The requester is an administrator of the domain to which the shared drive belongs.
For more information, see
Manage shared drives as domain administrators
. |
| enforceExpansiveAccess
(deprecated) | boolean
Deprecated: All requests use the expansive access rules. |

A plain text custom message to include in the notification email.

boolean

Deprecated: See
moveToNewOwnersRoot
for details.

This parameter only takes effect if the item isn't in a shared drive and the request is attempting to transfer the ownership of the item. If set to
true
, the item is moved to the new owner's My Drive root folder and all prior parents removed. If set to
false
, parents aren't changed.

Whether to send a notification email when sharing to users or groups. This defaults to
true
for users and groups, and is not allowed for other requests. It must not be disabled for ownership transfers.

Whether the requesting application supports both My Drives and shared drives.

Deprecated: Use
supportsAllDrives
instead.

Whether to transfer ownership to the specified user and downgrade the current owner to a writer. This parameter is required as an acknowledgement of the side effect. For more information, see
Transfer file ownership
.

Issue the request as a domain administrator.

If set to
true
, and if the following additional conditions are met, the requester is granted access:

- The file ID parameter refers to a shared drive.
- The requester is an administrator of the domain to which the shared drive belongs.
For more information, see
Manage shared drives as domain administrators
.

Deprecated: All requests use the expansive access rules.


### Request body

The request body contains an instance of
Permission
.


### Response body

If successful, the response body contains a newly created instance of
Permission
.


### Authorization scopes

Requires one of the following OAuth scopes:

- https://www.googleapis.com/auth/drive
- https://www.googleapis.com/auth/drive.file
Some scopes are restricted and require a security assessment for your app to use them. For more information, see the
Authorization guide
.

Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2026-02-24 UTC.


---

# Method: permissions.delete Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/reference/rest/v3/permissions/delete

- Home
- Google Workspace
- Google Drive
- Reference
- HTTP request
- Path parameters
- Query parameters
- Request body
- Response body
- Authorization scopes
- Try it!
Deletes a permission. For more information, see
Share files, folders, and drives
.

Warning:
Concurrent permissions operations on the same file aren't supported; only the last update is applied.


### HTTP request

DELETE https://www.googleapis.com/drive/v3/files/{fileId}/permissions/{permissionId}

The URL uses
gRPC Transcoding
syntax.


### Path parameters


| Parameters |  |
| --- | --- |
| fileId | string
The ID of the file or shared drive. |
| permissionId | string
The ID of the permission. |

string

The ID of the file or shared drive.

The ID of the permission.


### Query parameters


| Parameters |  |
| --- | --- |
| supportsAllDrives | boolean
Whether the requesting application supports both My Drives and shared drives. |
| supportsTeamDrives
(deprecated) | boolean
Deprecated: Use
supportsAllDrives
instead. |
| useDomainAdminAccess | boolean
Issue the request as a domain administrator.
If set to
true
, and if the following additional conditions are met, the requester is granted access:
The file ID parameter refers to a shared drive.
The requester is an administrator of the domain to which the shared drive belongs.
For more information, see
Manage shared drives as domain administrators
. |
| enforceExpansiveAccess
(deprecated) | boolean
Deprecated: All requests use the expansive access rules. |

boolean

Whether the requesting application supports both My Drives and shared drives.

Deprecated: Use
supportsAllDrives
instead.

Issue the request as a domain administrator.

If set to
true
, and if the following additional conditions are met, the requester is granted access:

- The file ID parameter refers to a shared drive.
- The requester is an administrator of the domain to which the shared drive belongs.
For more information, see
Manage shared drives as domain administrators
.

Deprecated: All requests use the expansive access rules.


### Request body

The request body must be empty.


### Response body

If successful, the response body is an empty JSON object.


### Authorization scopes

Requires one of the following OAuth scopes:

- https://www.googleapis.com/auth/drive
- https://www.googleapis.com/auth/drive.file
Some scopes are restricted and require a security assessment for your app to use them. For more information, see the
Authorization guide
.

Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2026-02-24 UTC.


---

# Method: permissions.get Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/reference/rest/v3/permissions/get

- Home
- Google Workspace
- Google Drive
- Reference
- HTTP request
- Path parameters
- Query parameters
- Request body
- Response body
- Authorization scopes
- Try it!
Gets a permission by ID. For more information, see
Share files, folders, and drives
.


### HTTP request

GET https://www.googleapis.com/drive/v3/files/{fileId}/permissions/{permissionId}

The URL uses
gRPC Transcoding
syntax.


### Path parameters


| Parameters |  |
| --- | --- |
| fileId | string
The ID of the file. |
| permissionId | string
The ID of the permission. |

string

The ID of the file.

The ID of the permission.


### Query parameters


| Parameters |  |
| --- | --- |
| supportsAllDrives | boolean
Whether the requesting application supports both My Drives and shared drives. |
| supportsTeamDrives
(deprecated) | boolean
Deprecated: Use
supportsAllDrives
instead. |
| useDomainAdminAccess | boolean
Issue the request as a domain administrator.
If set to
true
, and if the following additional conditions are met, the requester is granted access:
The file ID parameter refers to a shared drive.
The requester is an administrator of the domain to which the shared drive belongs.
For more information, see
Manage shared drives as domain administrators
. |

boolean

Whether the requesting application supports both My Drives and shared drives.

Deprecated: Use
supportsAllDrives
instead.

Issue the request as a domain administrator.

If set to
true
, and if the following additional conditions are met, the requester is granted access:

- The file ID parameter refers to a shared drive.
- The requester is an administrator of the domain to which the shared drive belongs.
For more information, see
Manage shared drives as domain administrators
.


### Request body

The request body must be empty.


### Response body

If successful, the response body contains an instance of
Permission
.


### Authorization scopes

Requires one of the following OAuth scopes:

- https://www.googleapis.com/auth/drive
- https://www.googleapis.com/auth/drive.file
- https://www.googleapis.com/auth/drive.meet.readonly
- https://www.googleapis.com/auth/drive.metadata
- https://www.googleapis.com/auth/drive.metadata.readonly
- https://www.googleapis.com/auth/drive.photos.readonly
- https://www.googleapis.com/auth/drive.readonly
Some scopes are restricted and require a security assessment for your app to use them. For more information, see the
Authorization guide
.

Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2025-10-06 UTC.


---

# Method: permissions.list Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/reference/rest/v3/permissions/list

- Home
- Google Workspace
- Google Drive
- Reference
- HTTP request
- Path parameters
- Query parameters
- Request body
- Response body
JSON representation
- JSON representation
- Authorization scopes
- Try it!
Lists a file's or shared drive's permissions. For more information, see
Share files, folders, and drives
.


### HTTP request

GET https://www.googleapis.com/drive/v3/files/{fileId}/permissions

The URL uses
gRPC Transcoding
syntax.


### Path parameters


| Parameters |  |
| --- | --- |
| fileId | string
The ID of the file or shared drive. |

string

The ID of the file or shared drive.


### Query parameters


| Parameters |  |
| --- | --- |
| pageSize | integer
The maximum number of permissions to return per page. When not set for files in a shared drive, at most 100 results will be returned. When not set for files that are not in a shared drive, the entire list will be returned. |
| pageToken | string
The token for continuing a previous list request on the next page. This should be set to the value of
nextPageToken
from the previous response. |
| supportsAllDrives | boolean
Whether the requesting application supports both My Drives and shared drives. |
| supportsTeamDrives
(deprecated) | boolean
Deprecated: Use
supportsAllDrives
instead. |
| useDomainAdminAccess | boolean
Issue the request as a domain administrator.
If set to
true
, and if the following additional conditions are met, the requester is granted access:
The file ID parameter refers to a shared drive.
The requester is an administrator of the domain to which the shared drive belongs.
For more information, see
Manage shared drives as domain administrators
. |
| includePermissionsForView | string
Specifies which additional view's permissions to include in the response. Only
published
is supported. |

integer

The maximum number of permissions to return per page. When not set for files in a shared drive, at most 100 results will be returned. When not set for files that are not in a shared drive, the entire list will be returned.

The token for continuing a previous list request on the next page. This should be set to the value of
nextPageToken
from the previous response.

boolean

Whether the requesting application supports both My Drives and shared drives.

Deprecated: Use
supportsAllDrives
instead.

Issue the request as a domain administrator.

If set to
true
, and if the following additional conditions are met, the requester is granted access:

- The file ID parameter refers to a shared drive.
- The requester is an administrator of the domain to which the shared drive belongs.
For more information, see
Manage shared drives as domain administrators
.

Specifies which additional view's permissions to include in the response. Only
published
is supported.


### Request body

The request body must be empty.


### Response body

A list of permissions for a file.

If successful, the response body contains data with the following structure:


| JSON representation |
| --- |
| {
"permissions"
:
[
{
object (
Permission
)
}
]
,
"nextPageToken"
:
string
,
"kind"
:
string
} |


```json
{
"permissions"
:
[
{
object (
Permission
)
}
]
,
"nextPageToken"
:
string
,
"kind"
:
string
}
```


| Fields |  |
| --- | --- |
| permissions[] | object (
Permission
)
The list of permissions. If
nextPageToken
is populated, then this list may be incomplete and an additional page of results should be fetched. |
| nextPageToken | string
The page token for the next page of permissions. This field will be absent if the end of the permissions list has been reached. If the token is rejected for any reason, it should be discarded, and pagination should be restarted from the first page of results. The page token is typically valid for several hours. However, if new items are added or removed, your expected results might differ. |
| kind | string
Identifies what kind of resource this is. Value: the fixed string
"drive#permissionList"
. |

object (
Permission
)

The list of permissions. If
nextPageToken
is populated, then this list may be incomplete and an additional page of results should be fetched.

The page token for the next page of permissions. This field will be absent if the end of the permissions list has been reached. If the token is rejected for any reason, it should be discarded, and pagination should be restarted from the first page of results. The page token is typically valid for several hours. However, if new items are added or removed, your expected results might differ.

Identifies what kind of resource this is. Value: the fixed string
"drive#permissionList"
.


### Authorization scopes

Requires one of the following OAuth scopes:

- https://www.googleapis.com/auth/drive
- https://www.googleapis.com/auth/drive.file
- https://www.googleapis.com/auth/drive.meet.readonly
- https://www.googleapis.com/auth/drive.metadata
- https://www.googleapis.com/auth/drive.metadata.readonly
- https://www.googleapis.com/auth/drive.photos.readonly
- https://www.googleapis.com/auth/drive.readonly
Some scopes are restricted and require a security assessment for your app to use them. For more information, see the
Authorization guide
.

Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2025-10-06 UTC.


---

# Method: permissions.update Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/reference/rest/v3/permissions/update

- Home
- Google Workspace
- Google Drive
- Reference
- HTTP request
- Path parameters
- Query parameters
- Request body
- Response body
- Authorization scopes
- Try it!
Updates a permission with patch semantics. For more information, see
Share files, folders, and drives
.

Warning:
Concurrent permissions operations on the same file aren't supported; only the last update is applied.


### HTTP request

PATCH https://www.googleapis.com/drive/v3/files/{fileId}/permissions/{permissionId}

The URL uses
gRPC Transcoding
syntax.


### Path parameters


| Parameters |  |
| --- | --- |
| fileId | string
The ID of the file or shared drive. |
| permissionId | string
The ID of the permission. |

string

The ID of the file or shared drive.

The ID of the permission.


### Query parameters


| Parameters |  |
| --- | --- |
| removeExpiration | boolean
Whether to remove the expiration date. |
| supportsAllDrives | boolean
Whether the requesting application supports both My Drives and shared drives. |
| supportsTeamDrives
(deprecated) | boolean
Deprecated: Use
supportsAllDrives
instead. |
| transferOwnership | boolean
Whether to transfer ownership to the specified user and downgrade the current owner to a writer. This parameter is required as an acknowledgement of the side effect. For more information, see
Transfer file ownership
. |
| useDomainAdminAccess | boolean
Issue the request as a domain administrator.
If set to
true
, and if the following additional conditions are met, the requester is granted access:
The file ID parameter refers to a shared drive.
The requester is an administrator of the domain to which the shared drive belongs.
For more information, see
Manage shared drives as domain administrators
. |
| enforceExpansiveAccess
(deprecated) | boolean
Deprecated: All requests use the expansive access rules. |

boolean

Whether to remove the expiration date.

Whether the requesting application supports both My Drives and shared drives.

Deprecated: Use
supportsAllDrives
instead.

Whether to transfer ownership to the specified user and downgrade the current owner to a writer. This parameter is required as an acknowledgement of the side effect. For more information, see
Transfer file ownership
.

Issue the request as a domain administrator.

If set to
true
, and if the following additional conditions are met, the requester is granted access:

- The file ID parameter refers to a shared drive.
- The requester is an administrator of the domain to which the shared drive belongs.
For more information, see
Manage shared drives as domain administrators
.

Deprecated: All requests use the expansive access rules.


### Request body

The request body contains an instance of
Permission
.


### Response body

If successful, the response body contains an instance of
Permission
.


### Authorization scopes

Requires one of the following OAuth scopes:

- https://www.googleapis.com/auth/drive
- https://www.googleapis.com/auth/drive.file
Some scopes are restricted and require a security assessment for your app to use them. For more information, see the
Authorization guide
.

Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2026-02-24 UTC.


---

# REST Resource: replies Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/reference/rest/v3/replies

- Home
- Google Workspace
- Google Drive
- Reference
- Resource: Reply
JSON representation
- JSON representation
- Methods

## Resource: Reply

A reply to a comment on a file.

Some resource methods (such as
replies.update
) require a
replyId
. Use the
replies.list
method to retrieve the ID for a reply.


| JSON representation |
| --- |
| {
"mentionedEmailAddresses"
:
[
string
]
,
"id"
:
string
,
"kind"
:
string
,
"createdTime"
:
string
,
"modifiedTime"
:
string
,
"action"
:
string
,
"author"
:
{
object (
User
)
}
,
"deleted"
:
boolean
,
"htmlContent"
:
string
,
"content"
:
string
,
"assigneeEmailAddress"
:
string
} |


```json
{
"mentionedEmailAddresses"
:
[
string
]
,
"id"
:
string
,
"kind"
:
string
,
"createdTime"
:
string
,
"modifiedTime"
:
string
,
"action"
:
string
,
"author"
:
{
object (
User
)
}
,
"deleted"
:
boolean
,
"htmlContent"
:
string
,
"content"
:
string
,
"assigneeEmailAddress"
:
string
}
```


| Fields |  |
| --- | --- |
| mentionedEmailAddresses[] | string
Output only. A list of email addresses for users mentioned in this comment. If no users are mentioned, the list is empty. |
| id | string
Output only. The ID of the reply. |
| kind | string
Output only. Identifies what kind of resource this is. Value: the fixed string
"drive#reply"
. |
| createdTime | string
Output only. The time at which the reply was created (
RFC 3339 date-time
). |
| modifiedTime | string
Output only. The last time the reply was modified (
RFC 3339 date-time
). |
| action | string
The action the reply performed to the parent comment. The supported values are:
resolve
reopen |
| author | object (
User
)
Output only. The author of the reply. The author's email address and permission ID won't be populated. |
| deleted | boolean
Output only. Whether the reply has been deleted. A deleted reply has no content. |
| htmlContent | string
Output only. The content of the reply with HTML formatting. |
| content | string
The plain text content of the reply. This field is used for setting the content, while
htmlContent
should be displayed. This field is required by the
create
method if no
action
value is specified. |
| assigneeEmailAddress | string
Output only. The email address of the user assigned to this comment. If no user is assigned, the field is unset. |

string

Output only. A list of email addresses for users mentioned in this comment. If no users are mentioned, the list is empty.

Output only. The ID of the reply.

Output only. Identifies what kind of resource this is. Value: the fixed string
"drive#reply"
.

Output only. The time at which the reply was created (
RFC 3339 date-time
).

Output only. The last time the reply was modified (
RFC 3339 date-time
).

The action the reply performed to the parent comment. The supported values are:

- resolve
- reopen
object (
User
)

Output only. The author of the reply. The author's email address and permission ID won't be populated.

boolean

Output only. Whether the reply has been deleted. A deleted reply has no content.

Output only. The content of the reply with HTML formatting.

The plain text content of the reply. This field is used for setting the content, while
htmlContent
should be displayed. This field is required by the
create
method if no
action
value is specified.

Output only. The email address of the user assigned to this comment. If no user is assigned, the field is unset.


| Methods |  |
| --- | --- |
| create | Creates a reply to a comment. |
| delete | Deletes a reply. |
| get | Gets a reply by ID. |
| list | Lists a comment's replies. |
| update | Updates a reply with patch semantics. |


## Methods


### create


### delete


### get


### list


### update

Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2025-12-02 UTC.


---

# Method: replies.create Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/reference/rest/v3/replies/create

- Home
- Google Workspace
- Google Drive
- Reference
- HTTP request
- Path parameters
- Request body
- Response body
- Authorization scopes
- Try it!
Creates a reply to a comment. For more information, see
Manage comments and replies
.


### HTTP request

POST https://www.googleapis.com/drive/v3/files/{fileId}/comments/{commentId}/replies

The URL uses
gRPC Transcoding
syntax.


### Path parameters


| Parameters |  |
| --- | --- |
| fileId | string
The ID of the file. |
| commentId | string
The ID of the comment. |

string

The ID of the file.

The ID of the comment.


### Request body

The request body contains an instance of
Reply
.


### Response body

If successful, the response body contains a newly created instance of
Reply
.


### Authorization scopes

Requires one of the following OAuth scopes:

- https://www.googleapis.com/auth/drive
- https://www.googleapis.com/auth/drive.file
Some scopes are restricted and require a security assessment for your app to use them. For more information, see the
Authorization guide
.

Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2025-12-02 UTC.


---

# Method: replies.delete Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/reference/rest/v3/replies/delete

- Home
- Google Workspace
- Google Drive
- Reference
- HTTP request
- Path parameters
- Request body
- Response body
- Authorization scopes
- Try it!
Deletes a reply. For more information, see
Manage comments and replies
.


### HTTP request

DELETE https://www.googleapis.com/drive/v3/files/{fileId}/comments/{commentId}/replies/{replyId}

The URL uses
gRPC Transcoding
syntax.


### Path parameters


| Parameters |  |
| --- | --- |
| fileId | string
The ID of the file. |
| commentId | string
The ID of the comment. |
| replyId | string
The ID of the reply. |

string

The ID of the file.

The ID of the comment.

The ID of the reply.


### Request body

The request body must be empty.


### Response body

If successful, the response body is an empty JSON object.


### Authorization scopes

Requires one of the following OAuth scopes:

- https://www.googleapis.com/auth/drive
- https://www.googleapis.com/auth/drive.file
Some scopes are restricted and require a security assessment for your app to use them. For more information, see the
Authorization guide
.

Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2025-12-02 UTC.


---

# Method: replies.get Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/reference/rest/v3/replies/get

- Home
- Google Workspace
- Google Drive
- Reference
- HTTP request
- Path parameters
- Query parameters
- Request body
- Response body
- Authorization scopes
- Try it!
Gets a reply by ID. For more information, see
Manage comments and replies
.


### HTTP request

GET https://www.googleapis.com/drive/v3/files/{fileId}/comments/{commentId}/replies/{replyId}

The URL uses
gRPC Transcoding
syntax.


### Path parameters


| Parameters |  |
| --- | --- |
| fileId | string
The ID of the file. |
| commentId | string
The ID of the comment. |
| replyId | string
The ID of the reply. |

string

The ID of the file.

The ID of the comment.

The ID of the reply.


### Query parameters


| Parameters |  |
| --- | --- |
| includeDeleted | boolean
Whether to return deleted replies. Deleted replies don't include their original content. |

boolean

Whether to return deleted replies. Deleted replies don't include their original content.


### Request body

The request body must be empty.


### Response body

If successful, the response body contains an instance of
Reply
.


### Authorization scopes

Requires one of the following OAuth scopes:

- https://www.googleapis.com/auth/drive
- https://www.googleapis.com/auth/drive.file
- https://www.googleapis.com/auth/drive.meet.readonly
- https://www.googleapis.com/auth/drive.readonly
Some scopes are restricted and require a security assessment for your app to use them. For more information, see the
Authorization guide
.

Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2025-12-02 UTC.


---

# Method: replies.list Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/reference/rest/v3/replies/list

- Home
- Google Workspace
- Google Drive
- Reference
- HTTP request
- Path parameters
- Query parameters
- Request body
- Response body
JSON representation
- JSON representation
- Authorization scopes
- Try it!
Lists a comment's replies. For more information, see
Manage comments and replies
.


### HTTP request

GET https://www.googleapis.com/drive/v3/files/{fileId}/comments/{commentId}/replies

The URL uses
gRPC Transcoding
syntax.


### Path parameters


| Parameters |  |
| --- | --- |
| fileId | string
The ID of the file. |
| commentId | string
The ID of the comment. |

string

The ID of the file.

The ID of the comment.


### Query parameters


| Parameters |  |
| --- | --- |
| includeDeleted | boolean
Whether to include deleted replies. Deleted replies don't include their original content. |
| pageSize | integer
The maximum number of replies to return per page. |
| pageToken | string
The token for continuing a previous list request on the next page. This should be set to the value of
nextPageToken
from the previous response. |

boolean

Whether to include deleted replies. Deleted replies don't include their original content.

integer

The maximum number of replies to return per page.

The token for continuing a previous list request on the next page. This should be set to the value of
nextPageToken
from the previous response.


### Request body

The request body must be empty.


### Response body

A list of replies to a comment on a file.

If successful, the response body contains data with the following structure:


| JSON representation |
| --- |
| {
"replies"
:
[
{
object (
Reply
)
}
]
,
"kind"
:
string
,
"nextPageToken"
:
string
} |


```json
{
"replies"
:
[
{
object (
Reply
)
}
]
,
"kind"
:
string
,
"nextPageToken"
:
string
}
```


| Fields |  |
| --- | --- |
| replies[] | object (
Reply
)
The list of replies. If
nextPageToken
is populated, then this list may be incomplete and an additional page of results should be fetched. |
| kind | string
Identifies what kind of resource this is. Value: the fixed string
"drive#replyList"
. |
| nextPageToken | string
The page token for the next page of replies. This will be absent if the end of the replies list has been reached. If the token is rejected for any reason, it should be discarded, and pagination should be restarted from the first page of results. The page token is typically valid for several hours. However, if new items are added or removed, your expected results might differ. |

object (
Reply
)

The list of replies. If
nextPageToken
is populated, then this list may be incomplete and an additional page of results should be fetched.

Identifies what kind of resource this is. Value: the fixed string
"drive#replyList"
.

The page token for the next page of replies. This will be absent if the end of the replies list has been reached. If the token is rejected for any reason, it should be discarded, and pagination should be restarted from the first page of results. The page token is typically valid for several hours. However, if new items are added or removed, your expected results might differ.


### Authorization scopes

Requires one of the following OAuth scopes:

- https://www.googleapis.com/auth/drive
- https://www.googleapis.com/auth/drive.file
- https://www.googleapis.com/auth/drive.meet.readonly
- https://www.googleapis.com/auth/drive.readonly
Some scopes are restricted and require a security assessment for your app to use them. For more information, see the
Authorization guide
.

Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2025-12-02 UTC.


---

# Method: replies.update Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/reference/rest/v3/replies/update

- Home
- Google Workspace
- Google Drive
- Reference
- HTTP request
- Path parameters
- Request body
- Response body
- Authorization scopes
- Try it!
Updates a reply with patch semantics. For more information, see
Manage comments and replies
.


### HTTP request

PATCH https://www.googleapis.com/drive/v3/files/{fileId}/comments/{commentId}/replies/{replyId}

The URL uses
gRPC Transcoding
syntax.


### Path parameters


| Parameters |  |
| --- | --- |
| fileId | string
The ID of the file. |
| commentId | string
The ID of the comment. |
| replyId | string
The ID of the reply. |

string

The ID of the file.

The ID of the comment.

The ID of the reply.


### Request body

The request body contains an instance of
Reply
.


### Response body

If successful, the response body contains an instance of
Reply
.


### Authorization scopes

Requires one of the following OAuth scopes:

- https://www.googleapis.com/auth/drive
- https://www.googleapis.com/auth/drive.file
Some scopes are restricted and require a security assessment for your app to use them. For more information, see the
Authorization guide
.

Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2025-12-02 UTC.


---

# REST Resource: revisions Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/reference/rest/v3/revisions

- Home
- Google Workspace
- Google Drive
- Reference
- Resource: Revision
JSON representation
- JSON representation
- Methods

## Resource: Revision

The metadata for a revision to a file.

Some resource methods (such as
revisions.update
) require a
revisionId
. Use the
revisions.list
method to retrieve the ID for a revision.


| JSON representation |
| --- |
| {
"exportLinks"
:
{
string
:
string
,
...
}
,
"id"
:
string
,
"mimeType"
:
string
,
"kind"
:
string
,
"published"
:
boolean
,
"keepForever"
:
boolean
,
"md5Checksum"
:
string
,
"modifiedTime"
:
string
,
"publishAuto"
:
boolean
,
"publishedOutsideDomain"
:
boolean
,
"publishedLink"
:
string
,
"size"
:
string
,
"originalFilename"
:
string
,
"lastModifyingUser"
:
{
object (
User
)
}
} |


```json
{
"exportLinks"
:
{
string
:
string
,
...
}
,
"id"
:
string
,
"mimeType"
:
string
,
"kind"
:
string
,
"published"
:
boolean
,
"keepForever"
:
boolean
,
"md5Checksum"
:
string
,
"modifiedTime"
:
string
,
"publishAuto"
:
boolean
,
"publishedOutsideDomain"
:
boolean
,
"publishedLink"
:
string
,
"size"
:
string
,
"originalFilename"
:
string
,
"lastModifyingUser"
:
{
object (
User
)
}
}
```


| Fields |  |
| --- | --- |
| exportLinks | map (key: string, value: string)
Output only. Links for exporting Docs Editors files to specific formats.
An object containing a list of
"key": value
pairs. Example:
{ "name": "wrench", "mass": "1.3kg", "count": "3" }
. |
| id | string
Output only. The ID of the revision. |
| mimeType | string
Output only. The MIME type of the revision. |
| kind | string
Output only. Identifies what kind of resource this is. Value: the fixed string
"drive#revision"
. |
| published | boolean
Whether this revision is published. This is only applicable to Docs Editors files. |
| keepForever | boolean
Whether to keep this revision forever, even if it is no longer the head revision. If not set, the revision will be automatically purged 30 days after newer content is uploaded. This can be set on a maximum of 200 revisions for a file.
This field is only applicable to files with binary content in Drive. |
| md5Checksum | string
Output only. The MD5 checksum of the revision's content. This is only applicable to files with binary content in Drive. |
| modifiedTime | string
Output only. The last time the revision was modified (RFC 3339 date-time). |
| publishAuto | boolean
Whether subsequent revisions will be automatically republished. This is only applicable to Docs Editors files. |
| publishedOutsideDomain | boolean
Whether this revision is published outside the domain. This is only applicable to Docs Editors files. |
| publishedLink | string
Output only. A link to the published revision. This is only populated for Docs Editors files. |
| size | string (
int64
format)
Output only. The size of the revision's content in bytes. This is only applicable to files with binary content in Drive. |
| originalFilename | string
Output only. The original filename used to create this revision. This is only applicable to files with binary content in Drive. |
| lastModifyingUser | object (
User
)
Output only. The last user to modify this revision. This field is only populated when the last modification was performed by a signed-in user. |

map (key: string, value: string)

Output only. Links for exporting Docs Editors files to specific formats.

An object containing a list of
"key": value
pairs. Example:
{ "name": "wrench", "mass": "1.3kg", "count": "3" }
.

string

Output only. The ID of the revision.

Output only. The MIME type of the revision.

Output only. Identifies what kind of resource this is. Value: the fixed string
"drive#revision"
.

boolean

Whether this revision is published. This is only applicable to Docs Editors files.

Whether to keep this revision forever, even if it is no longer the head revision. If not set, the revision will be automatically purged 30 days after newer content is uploaded. This can be set on a maximum of 200 revisions for a file.

This field is only applicable to files with binary content in Drive.

Output only. The MD5 checksum of the revision's content. This is only applicable to files with binary content in Drive.

Output only. The last time the revision was modified (RFC 3339 date-time).

Whether subsequent revisions will be automatically republished. This is only applicable to Docs Editors files.

Whether this revision is published outside the domain. This is only applicable to Docs Editors files.

Output only. A link to the published revision. This is only populated for Docs Editors files.

string (
int64
format)

Output only. The size of the revision's content in bytes. This is only applicable to files with binary content in Drive.

Output only. The original filename used to create this revision. This is only applicable to files with binary content in Drive.

object (
User
)

Output only. The last user to modify this revision. This field is only populated when the last modification was performed by a signed-in user.


| Methods |  |
| --- | --- |
| delete | Permanently deletes a file version. |
| get | Gets a revision's metadata or content by ID. |
| list | Lists a file's revisions. |
| update | Updates a revision with patch semantics. |


## Methods


### delete


### get


### list


### update

Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2025-07-23 UTC.


---

# Method: revisions.delete Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/reference/rest/v3/revisions/delete

- Home
- Google Workspace
- Google Drive
- Reference
- HTTP request
- Path parameters
- Request body
- Response body
- Authorization scopes
- Try it!
Permanently deletes a file version. You can only delete revisions for files with binary content in Google Drive, like images or videos. Revisions for other files, like Google Docs or Sheets, and the last remaining file version can't be deleted. For more information, see
Manage file revisions
.


### HTTP request

DELETE https://www.googleapis.com/drive/v3/files/{fileId}/revisions/{revisionId}

The URL uses
gRPC Transcoding
syntax.


### Path parameters


| Parameters |  |
| --- | --- |
| fileId | string
The ID of the file. |
| revisionId | string
The ID of the revision. |

string

The ID of the file.

The ID of the revision.


### Request body

The request body must be empty.


### Response body

If successful, the response body is an empty JSON object.


### Authorization scopes

Requires one of the following OAuth scopes:

- https://www.googleapis.com/auth/drive
- https://www.googleapis.com/auth/drive.appdata
- https://www.googleapis.com/auth/drive.file
Some scopes are restricted and require a security assessment for your app to use them. For more information, see the
Authorization guide
.

Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2025-08-13 UTC.


---

# Method: revisions.get Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/reference/rest/v3/revisions/get

- Home
- Google Workspace
- Google Drive
- Reference
- HTTP request
- Path parameters
- Query parameters
- Request body
- Response body
- Authorization scopes
- Try it!
Gets a revision's metadata or content by ID. For more information, see
Manage file revisions
.


### HTTP request

GET https://www.googleapis.com/drive/v3/files/{fileId}/revisions/{revisionId}

The URL uses
gRPC Transcoding
syntax.


### Path parameters


| Parameters |  |
| --- | --- |
| fileId | string
The ID of the file. |
| revisionId | string
The ID of the revision. |

string

The ID of the file.

The ID of the revision.


### Query parameters


| Parameters |  |
| --- | --- |
| acknowledgeAbuse | boolean
Whether the user is acknowledging the risk of downloading known malware or other abusive files. This is only applicable when the
alt
parameter is set to
media
and the user is the owner of the file or an organizer of the shared drive in which the file resides. |

boolean

Whether the user is acknowledging the risk of downloading known malware or other abusive files. This is only applicable when the
alt
parameter is set to
media
and the user is the owner of the file or an organizer of the shared drive in which the file resides.


### Request body

The request body must be empty.


### Response body

If successful, the response body contains an instance of
Revision
.


### Authorization scopes

Requires one of the following OAuth scopes:

- https://www.googleapis.com/auth/drive
- https://www.googleapis.com/auth/drive.appdata
- https://www.googleapis.com/auth/drive.file
- https://www.googleapis.com/auth/drive.meet.readonly
- https://www.googleapis.com/auth/drive.metadata
- https://www.googleapis.com/auth/drive.metadata.readonly
- https://www.googleapis.com/auth/drive.photos.readonly
- https://www.googleapis.com/auth/drive.readonly
Some scopes are restricted and require a security assessment for your app to use them. For more information, see the
Authorization guide
.

Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2025-08-13 UTC.


---

# Method: revisions.list Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/reference/rest/v3/revisions/list

- Home
- Google Workspace
- Google Drive
- Reference
- HTTP request
- Path parameters
- Query parameters
- Request body
- Response body
JSON representation
- JSON representation
- Authorization scopes
- Try it!
Lists a file's revisions. For more information, see
Manage file revisions
.

Important:
The list of revisions returned by this method might be incomplete for files with a large revision history, including frequently edited Google Docs, Sheets, and Slides. Older revisions might be omitted from the response, meaning the first revision returned may not be the oldest existing revision. The revision history visible in the Workspace editor user interface might be more complete than the list returned by the API.


### HTTP request

GET https://www.googleapis.com/drive/v3/files/{fileId}/revisions

The URL uses
gRPC Transcoding
syntax.


### Path parameters


| Parameters |  |
| --- | --- |
| fileId | string
The ID of the file. |

string

The ID of the file.


### Query parameters


| Parameters |  |
| --- | --- |
| pageSize | integer
The maximum number of revisions to return per page. |
| pageToken | string
The token for continuing a previous list request on the next page. This should be set to the value of 'nextPageToken' from the previous response. |

integer

The maximum number of revisions to return per page.

The token for continuing a previous list request on the next page. This should be set to the value of 'nextPageToken' from the previous response.


### Request body

The request body must be empty.


### Response body

A list of revisions of a file.

If successful, the response body contains data with the following structure:


| JSON representation |
| --- |
| {
"revisions"
:
[
{
object (
Revision
)
}
]
,
"nextPageToken"
:
string
,
"kind"
:
string
} |


```json
{
"revisions"
:
[
{
object (
Revision
)
}
]
,
"nextPageToken"
:
string
,
"kind"
:
string
}
```


| Fields |  |
| --- | --- |
| revisions[] | object (
Revision
)
The list of revisions. If nextPageToken is populated, then this list may be incomplete and an additional page of results should be fetched. |
| nextPageToken | string
The page token for the next page of revisions. This will be absent if the end of the revisions list has been reached. If the token is rejected for any reason, it should be discarded, and pagination should be restarted from the first page of results. The page token is typically valid for several hours. However, if new items are added or removed, your expected results might differ. |
| kind | string
Identifies what kind of resource this is. Value: the fixed string
"drive#revisionList"
. |

object (
Revision
)

The list of revisions. If nextPageToken is populated, then this list may be incomplete and an additional page of results should be fetched.

The page token for the next page of revisions. This will be absent if the end of the revisions list has been reached. If the token is rejected for any reason, it should be discarded, and pagination should be restarted from the first page of results. The page token is typically valid for several hours. However, if new items are added or removed, your expected results might differ.

Identifies what kind of resource this is. Value: the fixed string
"drive#revisionList"
.


### Authorization scopes

Requires one of the following OAuth scopes:

- https://www.googleapis.com/auth/drive
- https://www.googleapis.com/auth/drive.appdata
- https://www.googleapis.com/auth/drive.file
- https://www.googleapis.com/auth/drive.meet.readonly
- https://www.googleapis.com/auth/drive.metadata
- https://www.googleapis.com/auth/drive.metadata.readonly
- https://www.googleapis.com/auth/drive.photos.readonly
- https://www.googleapis.com/auth/drive.readonly
Some scopes are restricted and require a security assessment for your app to use them. For more information, see the
Authorization guide
.

Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2025-11-10 UTC.


---

# Method: revisions.update Stay organized with collections Save and categorize content based on your preferences.

Source: https://developers.google.com/workspace/drive/api/reference/rest/v3/revisions/update

- Home
- Google Workspace
- Google Drive
- Reference
- HTTP request
- Path parameters
- Request body
- Response body
- Authorization scopes
- Try it!
Updates a revision with patch semantics. For more information, see
Manage file revisions
.


### HTTP request

PATCH https://www.googleapis.com/drive/v3/files/{fileId}/revisions/{revisionId}

The URL uses
gRPC Transcoding
syntax.


### Path parameters


| Parameters |  |
| --- | --- |
| fileId | string
The ID of the file. |
| revisionId | string
The ID of the revision. |

string

The ID of the file.

The ID of the revision.


### Request body

The request body contains an instance of
Revision
.


### Response body

If successful, the response body contains an instance of
Revision
.


### Authorization scopes

Requires one of the following OAuth scopes:

- https://www.googleapis.com/auth/drive
- https://www.googleapis.com/auth/drive.appdata
- https://www.googleapis.com/auth/drive.file
Some scopes are restricted and require a security assessment for your app to use them. For more information, see the
Authorization guide
.

Except as otherwise noted, the content of this page is licensed under the
Creative Commons Attribution 4.0 License
, and code samples are licensed under the
Apache 2.0 License
. For details, see the
Google Developers Site Policies
. Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2025-08-13 UTC.


---
