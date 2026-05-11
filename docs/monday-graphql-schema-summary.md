# monday.com GraphQL Schema Summary

API version: 2025-04

## Queries

### `account: Account`

Get the connected account's information.

### `account_connections(withAutomations: Boolean, withStateValidation: Boolean, page: Int, pageSize: Int, order: String, pagination: PaginationInput): [Connection!]`

Returns all connections for the account. Requires admin privileges.

### `account_roles: [AccountRole!]`

Get all roles for the account

### `account_trigger_statistics(filters: AccountTriggerStatisticsFiltersInput): AccountTriggerStatistics`

Get aggregated automation runs statistics in the account

### `account_triggers_statistics_by_entity_id(run_status: TriggerEventState!, filters: AccountTriggersByEntityIdFiltersInput): AccountTriggersByEntityId`

Get aggregated automation runs statistics grouped by entity Ids

### `app(id: ID!): AppType`

Get an app by ID or slug.

### `app_installs(account_id: ID, app_id: ID!, limit: Int, page: Int): [AppInstall]`

Get a collection of installs of an app.

### `app_subscription: [AppSubscription]`

Get the current app subscription. Note: This query does not work in the playground

### `app_subscription_operations(kind: String): AppSubscriptionOperationsCounter`

Get operations counter current value

### `app_subscriptions(app_id: ID!, status: SubscriptionStatus, account_id: Int, cursor: String, limit: Int): AppSubscriptions!`

### `apps_monetization_info: AppsMonetizationInfo`

Get apps monetization information for an account

### `apps_monetization_status: AppMonetizationStatus`

Get apps monetization status for an account

### `assets(ids: [ID!]!): [Asset]`

Get a collection of assets by ids.

### `block_events(triggerUuid: String!, nextPageOffset: Int): BlockEventsPage`

List block events for a given trigger UUID

### `board_candidates(workspaceId: String!, usageType: BoardUsage!): [Board!]`

Get board candidates based on workspace and usage type

### `boards(board_kind: BoardKind, ids: [ID!], latest: Boolean, limit: Int, order_by: BoardsOrderBy, page: Int, state: State, workspace_ids: [ID]): [Board]`

Get a collection of boards.

### `complexity: Complexity`

Get the complexity data of your queries.

### `connection(id: Int!): Connection`

Fetch a single connection by its unique ID.

### `connection_board_ids(connectionId: Int!): [Int!]`

Get board IDs that are linked to a specific connection.

### `connections(withAutomations: Boolean, connectionState: String, withStateValidation: Boolean, page: Int, pageSize: Int, order: String, withPartialScopes: Boolean, pagination: PaginationInput): [Connection!]`

Returns connections for the authenticated user. Supports filtering, pagination, ordering, and partial-scope options.

### `custom_activity(ids: [String!], name: String, icon_id: CustomActivityIcon, color: CustomActivityColor): [CustomActivity!]`

### `dependency_column_config(board_id: ID!, account_id: ID!, user_id: ID!): DependencyColumnConfigResult`

Fetch dependency column configuration for a board

### `docs(ids: [ID!], limit: Int, object_ids: [ID!], order_by: DocsOrderBy, page: Int, workspace_ids: [ID]): [Document]`

Get a collection of docs.

### `empty: String`

Placeholder query field for automations-test microservice.
This can be replaced with actual queries as the service evolves.

### `export_events(board_id: ID, start_date: String, end_date: String, state: [String!], type: [String!], limit: Int, offset: Int, order_by: String, order_direction: String): EventsExport`

Export events for a board within a date range. Requires a valid X-Tool-Execution-Secret header.

### `export_graph(boardId: String!): BoardGraphExport`

Export the dependency graph for a specific board

### `folders(ids: [ID!], limit: Int, page: Int, workspace_ids: [ID]): [Folder]`

Get a collection of folders. Note: This query won't return folders from closed workspaces to which you are not subscribed

### `items(exclude_nonactive: Boolean, ids: [ID!], limit: Int, newest_first: Boolean, page: Int): [Item]`

Get a collection of items.

### `items_page_by_column_values(board_id: ID!, columns: [ItemsPageByColumnValuesQuery!], cursor: String, limit: Int!): ItemsResponse!`

Search items by multiple columns and values.

### `managed_column(id: [String!], state: [ManagedColumnState!]): [ManagedColumn!]`

Get managed column data.

### `marketplace_app_discounts(app_id: ID!): [MarketplaceAppDiscount!]!`

### `me: User`

Get the connected user's information.

### `next_items_page(cursor: String!, limit: Int!): ItemsResponse!`

Get next pages of board's items (rows) by cursor.

### `platform_api: PlatformApi`

Platform API data.

### `sprints(ids: [ID!]!): [Sprint!]`

Get a collection of monday dev sprints

### `tags(ids: [ID!]): [Tag]`

Get a collection of tags.

### `teams(ids: [ID!]): [Team]`

Get a collection of teams.

### `timeline(id: ID!): TimelineResponse`

Fetches timeline items for a given item

### `timeline_item(id: ID!): TimelineItem`

### `trigger_event(triggerUuid: String!): TriggerEvent`

Fetch a single trigger event by UUID

### `trigger_events(nextPageOffset: Int, filters: TriggerEventsFiltersInput): TriggerEventsPage`

List trigger events with optional filters

### `updates(limit: Int, page: Int, ids: [ID!]): [Update!]`

### `user_connections(withAutomations: Boolean, withStateValidation: Boolean, page: Int, pageSize: Int, order: String, pagination: PaginationInput): [Connection!]`

Returns connections that belong to the authenticated user.

### `users(emails: [String], ids: [ID!], kind: UserKind, limit: Int, name: String, newest_first: Boolean, non_active: Boolean, page: Int): [User]`

Get a collection of users.

### `version: Version!`

Get the API version in use

### `versions: [Version!]`

Get a list containing the versions of the API

### `webhooks(app_webhooks_only: Boolean, board_id: ID!): [Webhook]`

Get a collection of webhooks for the board

### `workspaces(ids: [ID!], kind: WorkspaceKind, limit: Int, order_by: WorkspacesOrderBy, page: Int, state: State): [Workspace]`

Get a collection of workspaces.

## Mutations

### `activate_managed_column(id: String!): ManagedColumn`

Activate managed column mutation.

### `activate_users(user_ids: [ID!]!): ActivateUsersResult`

Activates the specified users.

### `add_file_to_column(column_id: String!, file: File!, item_id: ID!): Asset`

Add a file to a column value.

### `add_file_to_update(file: File!, update_id: ID!): Asset`

Add a file to an update.

### `add_subscribers_to_board(board_id: ID!, kind: BoardSubscriberKind, user_ids: [ID!]!): [User]`

Add subscribers to a board.

Deprecated: use add_users_to_board instead

### `add_teams_to_board(board_id: ID!, kind: BoardSubscriberKind, team_ids: [ID!]!): [Team]`

Add teams subscribers to a board.

### `add_teams_to_workspace(kind: WorkspaceSubscriberKind, team_ids: [ID!]!, workspace_id: ID!): [Team]`

Add teams to a workspace.

### `add_users_to_board(board_id: ID!, kind: BoardSubscriberKind, user_ids: [ID!]!): [User]`

Add subscribers to a board.

### `add_users_to_team(team_id: ID!, user_ids: [ID!]!): ChangeTeamMembershipsResult`

Add users to team.

### `add_users_to_workspace(kind: WorkspaceSubscriberKind, user_ids: [ID!]!, workspace_id: ID!): [User]`

Add users to a workspace.

### `archive_board(board_id: ID!): Board`

Archive a board.

### `archive_group(board_id: ID!, group_id: String!): Group`

Archives a group in a specific board.

### `archive_item(item_id: ID): Item`

Archive an item.

### `assign_team_owners(team_id: ID!, user_ids: [ID!]!): AssignTeamOwnersResult`

Assigns the specified users as owners of the specified team.

### `batch_extend_trial_period(account_slugs: [String!]!, app_id: ID!, duration_in_days: Int!, plan_id: String!): BatchExtendTrialPeriod`

Extends trial period of an application to selected accounts

### `batch_update_dependency_column(boardId: String!, columnId: String!, values: [DependencyPulseValueInput!]!): JSON!`

Batch update the dependency column values in a board. Limited to 50 items per batch.

### `change_column_metadata(board_id: ID!, column_id: String!, column_property: ColumnProperty, value: String): Column`

Change a column's properties

### `change_column_title(board_id: ID!, column_id: String!, title: String!): Column`

Change a column's title

### `change_column_value(board_id: ID!, column_id: String!, create_labels_if_missing: Boolean, item_id: ID, value: JSON!): Item`

Change an item's column value.

### `change_multiple_column_values(board_id: ID!, column_values: JSON!, create_labels_if_missing: Boolean, item_id: ID): Item`

Changes the column values of a specific item.

### `change_simple_column_value(board_id: ID!, column_id: String!, create_labels_if_missing: Boolean, item_id: ID, value: String): Item`

Change an item's column with simple value.

### `clear_item_updates(item_id: ID!): Item`

Clear an item's updates.

### `complexity: Complexity`

Get the complexity data of your mutations.

### `create_board(board_kind: BoardKind!, board_name: String!, board_owner_ids: [ID!], board_owner_team_ids: [ID!], board_subscriber_ids: [ID!], board_subscriber_teams_ids: [ID!], description: String, empty: Boolean, folder_id: ID, template_id: ID, workspace_id: ID): Board`

Create a new board.

### `create_column(board_id: ID!, id: String, title: String!, description: String, after_column_id: ID, defaults: JSON, column_type: ColumnType!): Column`

Generic mutation for creating any column type with validation. Supports creating column with properties like title, description, and type-specific defaults/settings. The mutation validates input against the column type's schema before applying changes. Use get_column_type_schema query to understand available properties for each column type.

### `create_custom_activity(name: String!, icon_id: CustomActivityIcon!, color: CustomActivityColor!): CustomActivity`

### `create_doc(location: CreateDocInput!): Document`

Create a new doc.

### `create_doc_block(after_block_id: String, content: JSON!, doc_id: ID!, parent_block_id: String, type: DocBlockContentType!): DocumentBlock`

Create new document block

### `create_dropdown_managed_column(title: String!, description: String, settings: CreateDropdownColumnSettingsInput): DropdownManagedColumn`

Create managed column of type dropdown mutation.

### `create_folder(color: FolderColor, custom_icon: FolderCustomIcon, font_weight: FolderFontWeight, name: String!, parent_folder_id: ID, workspace_id: ID): Folder`

Creates a folder in a specific workspace.

### `create_group(board_id: ID!, group_color: String, group_name: String!, position: String, position_relative_method: PositionRelative, relative_to: String): Group`

Creates a new group in a specific board.

### `create_item(board_id: ID!, column_values: JSON, create_labels_if_missing: Boolean, group_id: String, item_name: String!, position_relative_method: PositionRelative, relative_to: ID): Item`

Create a new item.

### `create_notification(target_id: ID!, target_type: NotificationTargetType!, text: String!, user_id: ID!): Notification`

Create a new notification.

### `create_or_get_tag(board_id: ID, tag_name: String): Tag`

Create a new tag or get it if it already exists.

### `create_status_managed_column(title: String!, description: String, settings: CreateStatusColumnSettingsInput): StatusManagedColumn`

Create managed column of type status mutation.

### `create_subitem(column_values: JSON, create_labels_if_missing: Boolean, item_name: String!, parent_item_id: ID!): Item`

Create subitem.

### `create_team(input: CreateTeamAttributesInput!, options: CreateTeamOptionsInput): Team`

Creates a new team.

### `create_timeline_item(item_id: ID!, user_id: Int, title: String!, timestamp: ISO8601DateTime!, summary: String, content: String, location: String, phone: String, url: String, time_range: TimelineItemTimeRange, custom_activity_id: String!): TimelineItem`

### `create_update(body: String!, item_id: ID, parent_id: ID): Update`

### `create_webhook(board_id: ID!, config: JSON, event: WebhookEventType!, url: String!): Webhook`

Create a new webhook.

### `create_workspace(account_product_id: ID, description: String, kind: WorkspaceKind!, name: String!): Workspace`

Create a new workspace.

### `deactivate_managed_column(id: String!): ManagedColumn`

Deactivate managed column mutation.

### `deactivate_users(user_ids: [ID!]!): DeactivateUsersResult`

Deactivates the specified users.

### `delete_board(board_id: ID!): Board`

Delete a board.

### `delete_column(board_id: ID!, column_id: String!): Column`

Deletes a column from a board. Cannot delete mandatory columns (e.g., name column).

### `delete_custom_activity(id: String!): CustomActivity`

### `delete_doc_block(block_id: String!): DocumentBlockIdOnly`

Delete a document block

### `delete_folder(folder_id: ID!): Folder`

Deletes a folder in a specific workspace.

### `delete_group(board_id: ID!, group_id: String!): Group`

Deletes a group in a specific board.

### `delete_item(item_id: ID): Item`

Delete an item.

### `delete_managed_column(id: String!): ManagedColumn`

Delete managed column mutation.

### `delete_marketplace_app_discount(app_id: ID!, account_slug: String!): DeleteMarketplaceAppDiscountResult!`

### `delete_subscribers_from_board(board_id: ID!, user_ids: [ID!]!): [User]`

Remove subscribers from the board.

### `delete_team(team_id: ID!): Team`

Deletes the specified team.

### `delete_teams_from_board(board_id: ID!, team_ids: [ID!]!): [Team]`

Remove team subscribers from the board.

### `delete_teams_from_workspace(team_ids: [ID!]!, workspace_id: ID!): [Team]`

Delete teams from a workspace.

### `delete_timeline_item(id: String!): TimelineItem`

### `delete_update(id: ID!): Update`

### `delete_users_from_workspace(user_ids: [ID!]!, workspace_id: ID!): [User]`

Delete users from a workspace.

### `delete_webhook(id: ID!): Webhook`

Delete a new webhook.

### `delete_workspace(workspace_id: ID!): Workspace`

Delete workspace.

### `duplicate_board(board_id: ID!, board_name: String, duplicate_type: DuplicateBoardType!, folder_id: ID, keep_subscribers: Boolean, workspace_id: ID): BoardDuplication`

Duplicate a board.

### `duplicate_group(add_to_top: Boolean, board_id: ID!, group_id: String!, group_title: String): Group`

Duplicate a group.

### `duplicate_item(board_id: ID!, item_id: ID, with_updates: Boolean): Item`

Duplicate an item.

### `edit_update(id: ID!, body: String!): Update!`

### `export_markdown_from_doc(docId: ID!, blockIds: [String!]): ExportMarkdownResult`

Converts document content into standard markdown format for external use, backup, or processing. Exports the entire document by default, or specific blocks if block IDs are provided. Use this to extract content for integration with other systems, create backups, generate reports, or process document content with external tools. The output is clean, portable markdown that preserves formatting and structure.

Deprecated: Please use the query export_markdown_from_doc instead.

### `grant_marketplace_app_discount(app_id: ID!, account_slug: String!, data: GrantMarketplaceAppDiscountData!): GrantMarketplaceAppDiscountResult!`

### `increase_app_subscription_operations(increment_by: Int, kind: String): AppSubscriptionOperationsCounter`

Increase operations counter

### `invite_users(emails: [String!]!, user_role: UserRole, product: Product): InviteUsersResult`

Invite users to the account.

### `like_update(update_id: ID!, reaction_type: String): Update`

### `move_item_to_board(board_id: ID!, columns_mapping: [ColumnMappingInput!], group_id: ID!, item_id: ID!, subitems_columns_mapping: [ColumnMappingInput!]): Item`

Move an item to a different board.

### `move_item_to_group(group_id: String!, item_id: ID): Item`

Move an item to a different group.

### `pin_to_top(id: ID!, item_id: ID): Update!`

### `remove_mock_app_subscription(app_id: ID!, partial_signing_secret: String!): AppSubscription`

Remove mock app subscription for the current account

### `remove_team_owners(team_id: ID!, user_ids: [ID!]!): RemoveTeamOwnersResult`

Removes the specified users as owners of the specified team.

### `remove_users_from_team(team_id: ID!, user_ids: [ID!]!): ChangeTeamMembershipsResult`

Remove users from team.

### `set_mock_app_subscription(app_id: ID!, billing_period: String, is_trial: Boolean, max_units: Int, partial_signing_secret: String!, plan_id: String, pricing_version: Int, renewal_date: Date): AppSubscription`

Set mock app subscription for the current account

### `unlike_update(update_id: ID!): Update!`

### `unpin_from_top(id: ID!, item_id: ID): Update!`

### `update_article_block(block_id: String!, content: JSON!): ArticleBlock`

Updates the content of a specific article block. The block must belong to a draft article that the user has permission to edit. Cannot update blocks of published articles.

### `update_assets_on_item(board_id: ID!, column_id: String!, files: [FileInput!]!, item_id: ID!): Item`

Update item column value by existing assets

### `update_board(board_attribute: BoardAttributes!, board_id: ID!, new_value: String!): JSON`

Update Board attribute.

### `update_dependency_column(boardId: String!, pulseId: String!, value: DependencyValueInput!, columnId: String!, successor_new_date: TimelineDateInput): JSON!`

Update the dependency column for a specific pulse

### `update_doc_block(block_id: String!, content: JSON!): DocumentBlock`

Update a document block

### `update_dropdown_managed_column(id: String!, title: String, description: String, settings: UpdateDropdownColumnSettingsInput, revision: Int!): DropdownManagedColumn`

Update managed column of type dropdown mutation.

### `update_email_domain(input: UpdateEmailDomainAttributesInput!): UpdateEmailDomainResult`

Updates the email domain for the specified users.

### `update_folder(color: FolderColor, custom_icon: FolderCustomIcon, folder_id: ID!, font_weight: FolderFontWeight, name: String, parent_folder_id: ID): Folder`

Updates a folder.

### `update_group(board_id: ID!, group_attribute: GroupAttributes!, group_id: String!, new_value: String!): Group`

Update an existing group.

### `update_multiple_users(user_updates: [UserUpdateInput!]!, bypass_confirmation_for_claimed_domains: Boolean): UpdateUserAttributesResult`

Updates attributes for users.

### `update_status_managed_column(id: String!, title: String, description: String, settings: UpdateStatusColumnSettingsInput, revision: Int!): StatusManagedColumn`

Update managed column of type status mutation.

### `update_users_role(user_ids: [ID!]!, new_role: BaseRoleName, role_id: ID): UpdateUsersRoleResult`

Updates the role of the specified users.

### `update_workspace(attributes: UpdateWorkspaceAttributesInput!, id: ID): Workspace`

Update an existing workspace.

### `use_template(board_kind: BoardKind, board_owner_ids: [Int], board_owner_team_ids: [Int], board_subscriber_ids: [Int], board_subscriber_teams_ids: [Int], callback_url_on_complete: String, destination_folder_id: Int, destination_folder_name: String, destination_name: String, destination_workspace_id: Int, skip_target_folder_creation: Boolean, solution_extra_options: JSON, template_id: Int!): Template`

Use a template

## Object / Input / Enum Types

### `Account` — OBJECT

Your monday.com account

| Field | Type | Deprecated |
|---|---|---|
| `active_members_count` | `Int` |  |
| `country_code` | `String` |  |
| `first_day_of_the_week` | `FirstDayOfTheWeek!` |  |
| `id` | `ID!` |  |
| `logo` | `String` |  |
| `name` | `String!` |  |
| `plan` | `Plan` |  |
| `products` | `[AccountProduct]` |  |
| `show_timeline_weekends` | `Boolean!` |  |
| `sign_up_product_kind` | `String` |  |
| `slug` | `String!` |  |
| `tier` | `String` |  |

### `AccountProduct` — OBJECT

The product a workspace is used in.

| Field | Type | Deprecated |
|---|---|---|
| `default_workspace_id` | `ID` |  |
| `id` | `ID` |  |
| `kind` | `String` |  |

### `AccountRole` — OBJECT

A role in the account

| Field | Type | Deprecated |
|---|---|---|
| `id` | `ID` |  |
| `name` | `String` |  |
| `roleType` | `String` |  |

### `AccountTriggerStatistics` — OBJECT

Aggregated automation runs statistics in the account

| Field | Type | Deprecated |
|---|---|---|
| `id` | `ID!` |  |
| `success` | `Int` |  |
| `failure` | `Int` |  |
| `total` | `Int` |  |

### `AccountTriggerStatisticsFiltersInput` — INPUT_OBJECT

Filters for account trigger statistics query

| Input field | Type | Default |
|---|---|---|
| `board_id` | `Int` | `` |
| `user_ids` | `[Int!]` | `` |

### `AccountTriggersByEntityId` — OBJECT

Aggregated automation runs statistics grouped by entity Ids

| Field | Type | Deprecated |
|---|---|---|
| `id` | `ID!` |  |
| `automation_statistics` | `JSON` |  |
| `workflow_statistics` | `JSON` |  |

### `AccountTriggersByEntityIdFiltersInput` — INPUT_OBJECT

Filters for account triggers statistics by entity Id query

| Input field | Type | Default |
|---|---|---|
| `board_id` | `Int` | `` |
| `automation_ids` | `[Int!]` | `` |
| `user_ids` | `[Int!]` | `` |

### `ActivateUsersError` — OBJECT

Error that occurred during activation.

| Field | Type | Deprecated |
|---|---|---|
| `message` | `String` |  |
| `code` | `ActivateUsersErrorCode` |  |
| `user_id` | `ID` |  |

### `ActivateUsersErrorCode` — ENUM

Error codes for activating users.

| Enum value | Deprecated |
|---|---|
| `EXCEEDS_BATCH_LIMIT` |  |
| `INVALID_INPUT` |  |
| `USER_NOT_FOUND` |  |
| `CANNOT_UPDATE_SELF` |  |
| `FAILED` |  |

### `ActivateUsersResult` — OBJECT

Result of activating users.

| Field | Type | Deprecated |
|---|---|---|
| `activated_users` | `[User!]` |  |
| `errors` | `[ActivateUsersError!]` |  |

### `ActivityLogType` — OBJECT

An activity log event

| Field | Type | Deprecated |
|---|---|---|
| `account_id` | `String!` |  |
| `created_at` | `String!` |  |
| `data` | `String!` |  |
| `entity` | `String!` |  |
| `event` | `String!` |  |
| `id` | `String!` |  |
| `user_id` | `String!` |  |

### `AppFeatureType` — OBJECT

| Field | Type | Deprecated |
|---|---|---|
| `id` | `ID!` |  |
| `created_at` | `Date` |  |
| `updated_at` | `Date` |  |
| `name` | `String` |  |
| `app_id` | `ID` |  |
| `type` | `String` |  |
| `data` | `JSON` |  |

### `AppInstall` — OBJECT

An app install details.

| Field | Type | Deprecated |
|---|---|---|
| `app_id` | `ID!` |  |
| `app_install_account` | `AppInstallAccount!` |  |
| `app_install_user` | `AppInstallUser!` |  |
| `app_version` | `AppVersion` |  |
| `permissions` | `AppInstallPermissions` |  |
| `timestamp` | `String` |  |

### `AppInstallAccount` — OBJECT

An app installer's account details

| Field | Type | Deprecated |
|---|---|---|
| `id` | `ID!` |  |

### `AppInstallPermissions` — OBJECT

The required and approved scopes for an app install.

| Field | Type | Deprecated |
|---|---|---|
| `approved_scopes` | `[String!]!` |  |
| `required_scopes` | `[String!]!` |  |

### `AppInstallUser` — OBJECT

An app installer's user details

| Field | Type | Deprecated |
|---|---|---|
| `id` | `ID` |  |

### `AppKind` — ENUM

The visibility type of an app

| Enum value | Deprecated |
|---|---|
| `PRIVATE` |  |
| `PUBLIC` |  |

### `AppMonetizationStatus` — OBJECT

The app monetization status for the current account

| Field | Type | Deprecated |
|---|---|---|
| `is_supported` | `Boolean!` |  |

### `AppStatus` — ENUM

The current state of an app based on its version status

| Enum value | Deprecated |
|---|---|
| `DRAFT` |  |
| `LIVE` |  |

### `AppSubscription` — OBJECT

The account subscription details for the app.

| Field | Type | Deprecated |
|---|---|---|
| `billing_period` | `String` |  |
| `days_left` | `Int` |  |
| `is_trial` | `Boolean` |  |
| `max_units` | `Int` |  |
| `plan_id` | `String!` |  |
| `pricing_version` | `Int` |  |
| `renewal_date` | `Date!` |  |

### `AppSubscriptionDetails` — OBJECT

Subscription object

| Field | Type | Deprecated |
|---|---|---|
| `account_id` | `Int!` |  |
| `plan_id` | `String!` |  |
| `pricing_version_id` | `Int!` |  |
| `monthly_price` | `Float!` |  |
| `currency` | `String!` |  |
| `period_type` | `SubscriptionPeriodType!` |  |
| `renewal_date` | `String` |  |
| `end_date` | `String` |  |
| `status` | `SubscriptionStatus!` |  |
| `discounts` | `[SubscriptionDiscount!]!` |  |
| `days_left` | `Int!` |  |

### `AppSubscriptionOperationsCounter` — OBJECT

The Operations counter response for the app action.

| Field | Type | Deprecated |
|---|---|---|
| `app_subscription` | `AppSubscription` |  |
| `counter_value` | `Int` |  |
| `kind` | `String!` |  |
| `period_key` | `String` |  |

### `AppSubscriptions` — OBJECT

| Field | Type | Deprecated |
|---|---|---|
| `subscriptions` | `[AppSubscriptionDetails!]!` |  |
| `total_count` | `Int!` |  |
| `cursor` | `String` |  |

### `AppType` — OBJECT

| Field | Type | Deprecated |
|---|---|---|
| `id` | `ID!` |  |
| `created_at` | `Date` |  |
| `updated_at` | `Date` |  |
| `name` | `String` |  |
| `api_app_id` | `ID` |  |
| `client_id` | `String` |  |
| `photo_url` | `String` |  |
| `photo_url_small` | `String` |  |
| `kind` | `AppKind` |  |
| `status` | `AppStatus` |  |
| `version_type` | `String` |  |
| `description` | `String` |  |
| `slug` | `String` |  |
| `permissions` | `[String!]` |  |
| `webhook_url` | `String` |  |
| `created_by` | `ID` |  |
| `account_id` | `ID` |  |
| `collaborators` | `[User!]` |  |
| `features` | `[AppFeatureType!]` |  |

### `AppVersion` — OBJECT

An app's version details.

| Field | Type | Deprecated |
|---|---|---|
| `major` | `Int!` |  |
| `minor` | `Int!` |  |
| `patch` | `Int!` |  |
| `text` | `String!` |  |
| `type` | `String` |  |

### `AppsMonetizationInfo` — OBJECT

The app monetization information for the current account

| Field | Type | Deprecated |
|---|---|---|
| `seats_count` | `Int` |  |

### `ArticleBlock` — OBJECT

The content blocks that make up the article.

| Field | Type | Deprecated |
|---|---|---|
| `id` | `ID` |  |
| `content` | `JSON` |  |
| `created_at` | `String` |  |
| `created_by` | `User` |  |
| `published_article_id` | `ID` |  |
| `parent_block_id` | `ID` |  |
| `position` | `Float` |  |
| `type` | `String` |  |
| `updated_at` | `String` |  |

### `Asset` — OBJECT

A file uploaded to monday.com

| Field | Type | Deprecated |
|---|---|---|
| `created_at` | `Date` |  |
| `file_extension` | `String!` |  |
| `file_size` | `Int!` |  |
| `id` | `ID!` |  |
| `name` | `String!` |  |
| `original_geometry` | `String` |  |
| `public_url` | `String!` |  |
| `uploaded_by` | `User!` |  |
| `url` | `String!` |  |
| `url_thumbnail` | `String` |  |

### `AssetsSource` — ENUM

The source of the asset

| Enum value | Deprecated |
|---|---|
| `all` |  |
| `columns` |  |
| `gallery` |  |

### `AssignTeamOwnersError` — OBJECT

Error that occurred while changing team owners.

| Field | Type | Deprecated |
|---|---|---|
| `message` | `String` |  |
| `code` | `AssignTeamOwnersErrorCode` |  |
| `user_id` | `ID` |  |

### `AssignTeamOwnersErrorCode` — ENUM

Error codes that can occur while changing team owners.

| Enum value | Deprecated |
|---|---|
| `VIEWERS_OR_GUESTS` |  |
| `USER_NOT_MEMBER_OF_TEAM` |  |
| `EXCEEDS_BATCH_LIMIT` |  |
| `INVALID_INPUT` |  |
| `USER_NOT_FOUND` |  |
| `CANNOT_UPDATE_SELF` |  |
| `FAILED` |  |

### `AssignTeamOwnersResult` — OBJECT

Result of changing the team's ownership.

| Field | Type | Deprecated |
|---|---|---|
| `team` | `Team` |  |
| `errors` | `[AssignTeamOwnersError!]` |  |

### `BaseRoleName` — ENUM

The role of the user.

| Enum value | Deprecated |
|---|---|
| `GUEST` |  |
| `VIEW_ONLY` |  |
| `MEMBER` |  |
| `ADMIN` |  |

### `BatchExtendTrialPeriod` — OBJECT

Result of an batch operation

| Field | Type | Deprecated |
|---|---|---|
| `details` | `[ExtendTrialPeriod!]` |  |
| `reason` | `String` |  |
| `success` | `Boolean!` |  |

### `BatteryValue` — OBJECT

A value showing status distribution counts

| Field | Type | Deprecated |
|---|---|---|
| `battery_value` | `[BatteryValueItem!]!` |  |
| `column` | `Column!` |  |
| `id` | `ID!` |  |
| `text` | `String` |  |
| `type` | `ColumnType!` |  |
| `value` | `JSON` |  |

### `BatteryValueItem` — OBJECT

A battery value item representing a status count

| Field | Type | Deprecated |
|---|---|---|
| `count` | `Int!` |  |
| `key` | `ID!` |  |

### `BlockEvent` — OBJECT

Automation block execution event

| Field | Type | Deprecated |
|---|---|---|
| `id` | `String` |  |
| `accountId` | `Int` |  |
| `userId` | `Int` |  |
| `boardId` | `Int` |  |
| `eventKind` | `String` |  |
| `eventState` | `String` |  |
| `triggerUuid` | `String` |  |
| `triggerStarted` | `Float` |  |
| `triggerStartedAt` | `ISO8601DateTime` |  |
| `blockStartTimestamp` | `Float` |  |
| `blockFinishTimestamp` | `Float` |  |
| `atomicActionId` | `String` |  |
| `title` | `String` |  |
| `conditionSatisfied` | `Boolean` |  |
| `workflowNodeId` | `Int` |  |
| `entityKind` | `String` |  |
| `billingActionCountForBlock` | `Int` |  |
| `errorReason` | `String` |  |

### `BlockEventsPage` — OBJECT

A page of block events

| Field | Type | Deprecated |
|---|---|---|
| `blockEvents` | `[BlockEvent!]` |  |

### `Board` — OBJECT

A monday.com board.

| Field | Type | Deprecated |
|---|---|---|
| `id` | `ID!` |  |
| `views` | `[BoardView]` |  |
| `updates` | `[Update!]` |  |
| `columns` | `[Column]` |  |
| `activity_logs` | `[ActivityLogType]` |  |
| `board_folder_id` | `ID` |  |
| `board_kind` | `BoardKind!` |  |
| `columns_namespace` | `String` |  |
| `communication` | `JSON` |  |
| `creator` | `User!` |  |
| `description` | `String` |  |
| `groups` | `[Group]` |  |
| `item_terminology` | `String` |  |
| `items_count` | `Int` |  |
| `items_limit` | `Int` |  |
| `items_page` | `ItemsResponse!` |  |
| `name` | `String!` |  |
| `owner` | `User!` | This field returned creator of the board. Please use 'creator' or 'owners' fields instead. |
| `owners` | `[User]!` |  |
| `permissions` | `String!` |  |
| `state` | `State!` |  |
| `subscribers` | `[User]!` |  |
| `tags` | `[Tag]` |  |
| `team_owners` | `[Team!]` |  |
| `team_subscribers` | `[Team!]` |  |
| `top_group` | `Group!` |  |
| `type` | `BoardObjectType` |  |
| `updated_at` | `ISO8601DateTime` |  |
| `url` | `String!` |  |
| `workspace` | `Workspace` |  |
| `workspace_id` | `ID` |  |

### `BoardAttributes` — ENUM

The board attributes available.

| Enum value | Deprecated |
|---|---|
| `communication` |  |
| `description` |  |
| `name` |  |

### `BoardDuplication` — OBJECT

A board duplication

| Field | Type | Deprecated |
|---|---|---|
| `board` | `Board!` |  |
| `is_async` | `Boolean!` |  |

### `BoardGraphExport` — OBJECT

The complete graph export for a board

| Field | Type | Deprecated |
|---|---|---|
| `boardId` | `String` |  |
| `graphData` | `JSON` |  |
| `exportedAt` | `String` |  |
| `nodeCount` | `Int` |  |
| `edgeCount` | `Int` |  |
| `graphAttributes` | `JSON` |  |
| `cycles` | `JSON` |  |

### `BoardKind` — ENUM

The board kinds available.

| Enum value | Deprecated |
|---|---|
| `private` |  |
| `public` |  |
| `share` |  |

### `BoardObjectType` — ENUM

The board object types.

| Enum value | Deprecated |
|---|---|
| `board` |  |
| `custom_object` |  |
| `document` |  |
| `sub_items_board` |  |

### `BoardRelationValue` — OBJECT

| Field | Type | Deprecated |
|---|---|---|
| `column` | `Column!` |  |
| `display_value` | `String!` |  |
| `id` | `ID!` |  |
| `linked_item_ids` | `[ID!]!` |  |
| `linked_items` | `[Item!]!` |  |
| `text` | `String` |  |
| `type` | `ColumnType!` |  |
| `updated_at` | `Date` |  |
| `value` | `JSON` |  |

### `BoardSubscriberKind` — ENUM

The board subscriber kind.

| Enum value | Deprecated |
|---|---|
| `owner` |  |
| `subscriber` |  |

### `BoardUsage` — ENUM

Enum representing different usage types for board operations

| Enum value | Deprecated |
|---|---|
| `CONVERT_TO_PROJECT` |  |
| `CONNECT_TO_PORTFOLIO` |  |

### `BoardView` — OBJECT

A board's view.

| Field | Type | Deprecated |
|---|---|---|
| `id` | `ID!` |  |
| `name` | `String!` |  |
| `type` | `String` |  |
| `settings_str` | `String!` |  |
| `view_specific_data_str` | `String!` |  |
| `source_view_id` | `ID` |  |

### `BoardsOrderBy` — ENUM

Options to order by.

| Enum value | Deprecated |
|---|---|
| `created_at` |  |
| `used_at` |  |

### `Boolean` — SCALAR

The `Boolean` scalar type represents `true` or `false`.

### `ButtonValue` — OBJECT

| Field | Type | Deprecated |
|---|---|---|
| `color` | `String` |  |
| `column` | `Column!` |  |
| `id` | `ID!` |  |
| `label` | `String` |  |
| `text` | `String` |  |
| `type` | `ColumnType!` |  |
| `value` | `JSON` |  |

### `ChangeTeamMembershipsResult` — OBJECT

The result of adding users to / removing users from a team.

| Field | Type | Deprecated |
|---|---|---|
| `failed_users` | `[User!]` |  |
| `successful_users` | `[User!]` |  |

### `CheckboxValue` — OBJECT

| Field | Type | Deprecated |
|---|---|---|
| `checked` | `Boolean` |  |
| `column` | `Column!` |  |
| `id` | `ID!` |  |
| `text` | `String` |  |
| `type` | `ColumnType!` |  |
| `updated_at` | `Date` |  |
| `value` | `JSON` |  |

### `ColorPickerValue` — OBJECT

| Field | Type | Deprecated |
|---|---|---|
| `color` | `String` |  |
| `column` | `Column!` |  |
| `id` | `ID!` |  |
| `text` | `String` |  |
| `type` | `ColumnType!` |  |
| `updated_at` | `Date` |  |
| `value` | `JSON` |  |

### `Column` — OBJECT

| Field | Type | Deprecated |
|---|---|---|
| `id` | `ID!` |  |
| `title` | `String!` |  |
| `description` | `String` |  |
| `type` | `ColumnType!` |  |
| `width` | `Int` |  |
| `archived` | `Boolean!` |  |
| `settings_str` | `String!` | From version 2025-10, use settings instead. Will be removed in a future version. |

### `ColumnMappingInput` — INPUT_OBJECT

An object defining a mapping of column between source board and destination board

| Input field | Type | Default |
|---|---|---|
| `source` | `ID!` | `` |
| `target` | `ID` | `` |

### `ColumnProperty` — ENUM

The property name of the column to be changed.

| Enum value | Deprecated |
|---|---|
| `description` |  |
| `title` |  |

### `ColumnSettings` — UNION

### `ColumnType` — ENUM

Types of columns supported by the API

| Enum value | Deprecated |
|---|---|
| `auto_number` |  |
| `board_relation` |  |
| `button` |  |
| `checkbox` |  |
| `color_picker` |  |
| `country` |  |
| `creation_log` |  |
| `date` |  |
| `dependency` |  |
| `doc` |  |
| `dropdown` |  |
| `email` |  |
| `file` |  |
| `formula` |  |
| `group` |  |
| `hour` |  |
| `integration` |  |
| `item_assignees` |  |
| `item_id` |  |
| `last_updated` |  |
| `link` |  |
| `location` |  |
| `long_text` |  |
| `mirror` |  |
| `numbers` |  |
| `people` |  |
| `phone` |  |
| `progress` |  |
| `rating` |  |
| `status` |  |
| `tags` |  |
| `team` |  |
| `text` |  |
| `timeline` |  |
| `time_tracking` |  |
| `vote` |  |
| `week` |  |
| `world_clock` |  |
| `unsupported` |  |
| `name` |  |
| `person` |  |
| `direct_doc` |  |
| `subtasks` |  |

### `ColumnValue` — INTERFACE

| Field | Type | Deprecated |
|---|---|---|
| `column` | `Column!` |  |
| `id` | `ID!` |  |
| `text` | `String` |  |
| `type` | `ColumnType!` |  |
| `value` | `JSON` |  |

### `CompareValue` — SCALAR

A string or number value for comparison

### `Complexity` — OBJECT

Complexity data.

| Field | Type | Deprecated |
|---|---|---|
| `after` | `Int!` |  |
| `before` | `Int!` |  |
| `query` | `Int!` |  |
| `reset_in_x_seconds` | `Int!` |  |

### `Connection` — OBJECT

Represents an integration connection between a monday.com account and an external service.

| Field | Type | Deprecated |
|---|---|---|
| `id` | `Int` |  |
| `accountId` | `Int` |  |
| `userId` | `Int` |  |
| `provider` | `String` |  |
| `name` | `String` |  |
| `method` | `String` |  |
| `providerAccountIdentifier` | `String` |  |
| `state` | `String` |  |
| `createdAt` | `String` |  |
| `updatedAt` | `String` |  |

### `Country` — OBJECT

| Field | Type | Deprecated |
|---|---|---|
| `code` | `String!` |  |
| `name` | `String!` |  |

### `CountryValue` — OBJECT

| Field | Type | Deprecated |
|---|---|---|
| `column` | `Column!` |  |
| `country` | `Country` |  |
| `id` | `ID!` |  |
| `text` | `String` |  |
| `type` | `ColumnType!` |  |
| `updated_at` | `Date` |  |
| `value` | `JSON` |  |

### `CreateDocBoardInput` — INPUT_OBJECT

| Input field | Type | Default |
|---|---|---|
| `column_id` | `String!` | `` |
| `item_id` | `ID!` | `` |

### `CreateDocInput` — INPUT_OBJECT

| Input field | Type | Default |
|---|---|---|
| `board` | `CreateDocBoardInput` | `` |
| `workspace` | `CreateDocWorkspaceInput` | `` |

### `CreateDocWorkspaceInput` — INPUT_OBJECT

| Input field | Type | Default |
|---|---|---|
| `folder_id` | `ID` | `` |
| `kind` | `BoardKind` | `` |
| `name` | `String!` | `` |
| `workspace_id` | `ID!` | `` |

### `CreateDropdownColumnSettingsInput` — INPUT_OBJECT

| Input field | Type | Default |
|---|---|---|
| `labels` | `[!]!` | `` |
| `limit_select` | `Boolean` | `` |
| `label_limit_count` | `Int` | `` |

### `CreateDropdownLabelInput` — INPUT_OBJECT

| Input field | Type | Default |
|---|---|---|
| `label` | `String!` | `` |

### `CreateStatusColumnSettingsInput` — INPUT_OBJECT

| Input field | Type | Default |
|---|---|---|
| `labels` | `[!]!` | `` |

### `CreateStatusLabelInput` — INPUT_OBJECT

| Input field | Type | Default |
|---|---|---|
| `label` | `String!` | `` |
| `color` | `StatusColumnColors!` | `` |
| `index` | `Int!` | `` |
| `description` | `String` | `` |
| `is_done` | `Boolean` | `` |

### `CreateTeamAttributesInput` — INPUT_OBJECT

Attributes of the team to be created.

| Input field | Type | Default |
|---|---|---|
| `name` | `String!` | `` |
| `is_guest_team` | `Boolean` | `` |
| `parent_team_id` | `ID` | `` |
| `subscriber_ids` | `[ID!]` | `` |

### `CreateTeamOptionsInput` — INPUT_OBJECT

Options for creating a team.

| Input field | Type | Default |
|---|---|---|
| `allow_empty_team` | `Boolean` | `` |

### `CreationLogValue` — OBJECT

| Field | Type | Deprecated |
|---|---|---|
| `column` | `Column!` |  |
| `created_at` | `Date!` |  |
| `creator` | `User!` |  |
| `creator_id` | `ID!` |  |
| `id` | `ID!` |  |
| `text` | `String` |  |
| `type` | `ColumnType!` |  |
| `value` | `JSON` |  |

### `CustomActivity` — OBJECT

| Field | Type | Deprecated |
|---|---|---|
| `id` | `ID` |  |
| `type` | `String` |  |
| `name` | `String` |  |
| `icon_id` | `CustomActivityIcon` |  |
| `color` | `CustomActivityColor` |  |

### `CustomActivityColor` — ENUM

| Enum value | Deprecated |
|---|---|
| `VIVID_CERULEAN` |  |
| `GO_GREEN` |  |
| `PHILIPPINE_GREEN` |  |
| `YANKEES_BLUE` |  |
| `CELTIC_BLUE` |  |
| `MEDIUM_TURQUOISE` |  |
| `CORNFLOWER_BLUE` |  |
| `MAYA_BLUE` |  |
| `SLATE_BLUE` |  |
| `GRAY` |  |
| `YELLOW_GREEN` |  |
| `DINGY_DUNGEON` |  |
| `PARADISE_PINK` |  |
| `BRINK_PINK` |  |
| `YELLOW_ORANGE` |  |
| `LIGHT_DEEP_PINK` |  |
| `LIGHT_HOT_PINK` |  |
| `PHILIPPINE_YELLOW` |  |

### `CustomActivityIcon` — ENUM

| Enum value | Deprecated |
|---|---|
| `ASCENDING` |  |
| `CAMERA` |  |
| `CONFERENCE` |  |
| `FLAG` |  |
| `GIFT` |  |
| `HEADPHONES` |  |
| `HOMEKEYS` |  |
| `LOCATION` |  |
| `PAPERPLANE` |  |
| `PLANE` |  |
| `NOTEBOOK` |  |
| `PLIERS` |  |
| `TRIPOD` |  |
| `TWOFLAGS` |  |
| `UTENCILS` |  |

### `CustomFieldMetas` — OBJECT

The custom fields meta data for user profile.

| Field | Type | Deprecated |
|---|---|---|
| `description` | `String` |  |
| `editable` | `Boolean` |  |
| `field_type` | `String` |  |
| `flagged` | `Boolean` |  |
| `icon` | `String` |  |
| `id` | `String` |  |
| `position` | `String` |  |
| `title` | `String` |  |

### `CustomFieldValue` — OBJECT

A custom field value for user profile.

| Field | Type | Deprecated |
|---|---|---|
| `custom_field_meta_id` | `String` |  |
| `value` | `String` |  |

### `DailyAnalytics` — OBJECT

API usage data.

| Field | Type | Deprecated |
|---|---|---|
| `last_updated` | `ISO8601DateTime` |  |
| `by_day` | `[PlatformApiDailyAnalyticsByDay!]` |  |
| `by_app` | `[PlatformApiDailyAnalyticsByApp!]` |  |
| `by_user` | `[PlatformApiDailyAnalyticsByUser!]` |  |

### `DailyLimit` — OBJECT

Platform API daily limit.

| Field | Type | Deprecated |
|---|---|---|
| `base` | `Int` |  |
| `total` | `Int` |  |

### `Date` — SCALAR

A date.

### `DateRangeInput` — INPUT_OBJECT

Date range filter (inclusive)

| Input field | Type | Default |
|---|---|---|
| `startDate` | `String!` | `` |
| `endDate` | `String!` | `` |

### `DateValue` — OBJECT

| Field | Type | Deprecated |
|---|---|---|
| `column` | `Column!` |  |
| `date` | `String` |  |
| `icon` | `String` |  |
| `id` | `ID!` |  |
| `text` | `String` |  |
| `time` | `String` |  |
| `type` | `ColumnType!` |  |
| `updated_at` | `Date` |  |
| `value` | `JSON` |  |

### `DeactivateUsersError` — OBJECT

Error that occurred during deactivation.

| Field | Type | Deprecated |
|---|---|---|
| `message` | `String` |  |
| `code` | `DeactivateUsersErrorCode` |  |
| `user_id` | `ID` |  |

### `DeactivateUsersErrorCode` — ENUM

Error codes for deactivating users.

| Enum value | Deprecated |
|---|---|
| `EXCEEDS_BATCH_LIMIT` |  |
| `INVALID_INPUT` |  |
| `USER_NOT_FOUND` |  |
| `CANNOT_UPDATE_SELF` |  |
| `FAILED` |  |

### `DeactivateUsersResult` — OBJECT

Result of deactivating users.

| Field | Type | Deprecated |
|---|---|---|
| `deactivated_users` | `[User!]` |  |
| `errors` | `[DeactivateUsersError!]` |  |

### `DeleteMarketplaceAppDiscount` — OBJECT

| Field | Type | Deprecated |
|---|---|---|
| `account_slug` | `String!` |  |
| `app_id` | `ID!` |  |

### `DeleteMarketplaceAppDiscountResult` — OBJECT

| Field | Type | Deprecated |
|---|---|---|
| `deleted_discount` | `DeleteMarketplaceAppDiscount!` |  |

### `DependencyColumnConfig` — OBJECT

Configuration record for a dependency column

| Field | Type | Deprecated |
|---|---|---|
| `id` | `ID` |  |
| `account_id` | `ID` |  |
| `board_id` | `ID` |  |
| `data` | `JSON` |  |
| `created_at` | `String` |  |
| `updated_at` | `String` |  |
| `config_type` | `String` |  |

### `DependencyColumnConfigResult` — OBJECT

Result containing dependency column configurations for a board

| Field | Type | Deprecated |
|---|---|---|
| `board_id` | `ID` |  |
| `dependency_columns` | `[DependencyColumnConfig!]` |  |

### `DependencyPulseValueInput` — INPUT_OBJECT

Input type for updating a single pulse dependency value

| Input field | Type | Default |
|---|---|---|
| `pulseId` | `ID!` | `` |
| `value` | `DependencyValueInput!` | `` |

### `DependencyRelation` — ENUM

Type of dependency relationship between items

| Enum value | Deprecated |
|---|---|
| `FS` |  |
| `SS` |  |
| `FF` |  |
| `SF` |  |

### `DependencyValue` — OBJECT

| Field | Type | Deprecated |
|---|---|---|
| `column` | `Column!` |  |
| `display_value` | `String!` |  |
| `id` | `ID!` |  |
| `linked_item_ids` | `[ID!]!` |  |
| `linked_items` | `[Item!]!` |  |
| `text` | `String` |  |
| `type` | `ColumnType!` |  |
| `updated_at` | `Date` |  |
| `value` | `JSON` |  |

### `DependencyValueInput` — INPUT_OBJECT

Input type for updating dependency column value, supporting both adding and removing dependencies

| Input field | Type | Default |
|---|---|---|
| `added_pulse` | `[UpdateDependencyColumnInput!]` | `` |
| `removed_pulse` | `[UpdateDependencyColumnInput!]` | `` |

### `DirectDocValue` — OBJECT

| Field | Type | Deprecated |
|---|---|---|
| `column` | `Column!` |  |
| `file` | `DirectDocValue` |  |
| `id` | `ID!` |  |
| `text` | `String` |  |
| `type` | `ColumnType!` |  |
| `value` | `JSON` |  |

### `DiscountPeriod` — ENUM

The period of a discount

| Enum value | Deprecated |
|---|---|
| `MONTHLY` |  |
| `YEARLY` |  |

### `DocBlockContentType` — ENUM

Various documents blocks types, such as text.

| Enum value | Deprecated |
|---|---|
| `bulleted_list` |  |
| `check_list` |  |
| `code` |  |
| `divider` |  |
| `image` |  |
| `large_title` |  |
| `layout` |  |
| `medium_title` |  |
| `normal_text` |  |
| `notice_box` |  |
| `numbered_list` |  |
| `page_break` |  |
| `quote` |  |
| `small_title` |  |
| `table` |  |
| `video` |  |

### `DocValue` — OBJECT

| Field | Type | Deprecated |
|---|---|---|
| `column` | `Column!` |  |
| `file` | `FileDocValue` |  |
| `id` | `ID!` |  |
| `text` | `String` |  |
| `type` | `ColumnType!` |  |
| `value` | `JSON` |  |

### `DocsOrderBy` — ENUM

Options to order by.

| Enum value | Deprecated |
|---|---|
| `created_at` |  |
| `used_at` |  |

### `Document` — OBJECT

Represents a monday.com doc - a rich-text page built from editable blocks (text, files, embeds, etc.).
  A doc can belong to:
  (1) a workspace (left-pane doc),
  (2) an item (doc on column),
  (3) a board view (doc as a board view).

| Field | Type | Deprecated |
|---|---|---|
| `id` | `ID!` |  |
| `object_id` | `ID!` |  |
| `blocks` | `[DocumentBlock]` |  |
| `created_at` | `Date` |  |
| `created_by` | `User` |  |
| `doc_folder_id` | `ID` |  |
| `doc_kind` | `BoardKind!` |  |
| `name` | `String!` |  |
| `relative_url` | `String` |  |
| `settings` | `JSON` |  |
| `updated_at` | `Date` |  |
| `url` | `String` |  |
| `workspace` | `Workspace` |  |
| `workspace_id` | `ID` |  |

### `DocumentBlock` — OBJECT

A monday.com document block.

| Field | Type | Deprecated |
|---|---|---|
| `content` | `JSON` |  |
| `created_at` | `Date` |  |
| `created_by` | `User` |  |
| `doc_id` | `ID` |  |
| `id` | `String!` |  |
| `parent_block_id` | `String` |  |
| `position` | `Float` |  |
| `type` | `String` |  |
| `updated_at` | `Date` |  |

### `DocumentBlockIdOnly` — OBJECT

A monday.com doc block.

| Field | Type | Deprecated |
|---|---|---|
| `id` | `String!` |  |

### `DropdownColumnSettings` — OBJECT

| Field | Type | Deprecated |
|---|---|---|
| `type` | `ManagedColumnTypes` |  |
| `labels` | `[DropdownLabel!]` |  |

### `DropdownLabel` — OBJECT

| Field | Type | Deprecated |
|---|---|---|
| `id` | `Int` |  |
| `label` | `String` |  |
| `is_deactivated` | `Boolean` |  |

### `DropdownManagedColumn` — OBJECT

| Field | Type | Deprecated |
|---|---|---|
| `id` | `String` |  |
| `title` | `String` |  |
| `description` | `String` |  |
| `settings_json` | `JSON` |  |
| `created_by` | `ID` |  |
| `updated_by` | `ID` |  |
| `revision` | `Int` |  |
| `state` | `ManagedColumnState` |  |
| `created_at` | `Date` |  |
| `updated_at` | `Date` |  |
| `settings` | `DropdownColumnSettings` |  |

### `DropdownValue` — OBJECT

| Field | Type | Deprecated |
|---|---|---|
| `column` | `Column!` |  |
| `id` | `ID!` |  |
| `text` | `String` |  |
| `type` | `ColumnType!` |  |
| `value` | `JSON` |  |
| `values` | `[DropdownValueOption!]!` |  |

### `DropdownValueOption` — OBJECT

| Field | Type | Deprecated |
|---|---|---|
| `id` | `ID!` |  |
| `label` | `String!` |  |

### `DuplicateBoardType` — ENUM

The board duplicate types available.

| Enum value | Deprecated |
|---|---|
| `duplicate_board_with_pulses` |  |
| `duplicate_board_with_pulses_and_updates` |  |
| `duplicate_board_with_structure` |  |

### `EmailValue` — OBJECT

| Field | Type | Deprecated |
|---|---|---|
| `column` | `Column!` |  |
| `email` | `String` |  |
| `id` | `ID!` |  |
| `label` | `String` |  |
| `text` | `String` |  |
| `type` | `ColumnType!` |  |
| `updated_at` | `Date` |  |
| `value` | `JSON` |  |

### `Event` — OBJECT

A single event record

| Field | Type | Deprecated |
|---|---|---|
| `id` | `ID` |  |
| `type` | `String` |  |
| `state` | `String` |  |
| `board_id` | `ID` |  |
| `event_data` | `JSON` |  |
| `origin_last_updated` | `String` |  |
| `created_at` | `String` |  |
| `updated_at` | `String` |  |

### `EventsExport` — OBJECT

Paginated export of events

| Field | Type | Deprecated |
|---|---|---|
| `events` | `[Event!]` |  |
| `total` | `Int` |  |
| `limit` | `Int` |  |
| `offset` | `Int` |  |

### `ExportMarkdownResult` — OBJECT

Response from exporting document content as markdown. Contains the generated markdown text or error details.

| Field | Type | Deprecated |
|---|---|---|
| `success` | `Boolean!` |  |
| `markdown` | `String` |  |
| `error` | `String` |  |

### `ExtendTrialPeriod` — OBJECT

Result of a single operation

| Field | Type | Deprecated |
|---|---|---|
| `account_slug` | `String!` |  |
| `reason` | `String` |  |
| `success` | `Boolean!` |  |

### `File` — SCALAR

A file

### `FileAssetInvalidValue` — OBJECT

A file with an invalid or missing asset.

| Field | Type | Deprecated |
|---|---|---|
| `asset_id` | `ID!` |  |
| `created_at` | `Date!` |  |
| `creator` | `User` |  |
| `creator_id` | `ID` |  |
| `error` | `String!` |  |
| `name` | `String` |  |

### `FileAssetValue` — OBJECT

| Field | Type | Deprecated |
|---|---|---|
| `asset` | `Asset!` |  |
| `asset_id` | `ID!` |  |
| `created_at` | `Date!` |  |
| `creator` | `User` |  |
| `creator_id` | `ID` |  |
| `is_image` | `Boolean!` |  |
| `name` | `String!` |  |

### `FileColumnValue` — ENUM

The type of a link value stored inside a file column

| Enum value | Deprecated |
|---|---|
| `asset` |  |
| `box` |  |
| `doc` |  |
| `dropbox` |  |
| `google_drive` |  |
| `link` |  |
| `onedrive` |  |

### `FileDocValue` — OBJECT

| Field | Type | Deprecated |
|---|---|---|
| `created_at` | `Date!` |  |
| `creator` | `User` |  |
| `creator_id` | `ID` |  |
| `doc` | `Document!` |  |
| `file_id` | `ID!` |  |
| `object_id` | `ID!` |  |
| `url` | `String` |  |

### `FileInput` — INPUT_OBJECT

| Input field | Type | Default |
|---|---|---|
| `assetId` | `ID` | `` |
| `fileType` | `FileColumnValue!` | `` |
| `linkToFile` | `String` | `` |
| `name` | `String!` | `` |
| `objectId` | `ID` | `` |

### `FileLinkValue` — OBJECT

| Field | Type | Deprecated |
|---|---|---|
| `created_at` | `Date!` |  |
| `creator` | `User` |  |
| `creator_id` | `ID` |  |
| `file_id` | `ID!` |  |
| `kind` | `FileLinkValueKind!` |  |
| `name` | `String!` |  |
| `url` | `String` |  |

### `FileLinkValueKind` — ENUM

The type of a link value stored inside a file column

| Enum value | Deprecated |
|---|---|
| `box` |  |
| `dropbox` |  |
| `google_drive` |  |
| `link` |  |
| `onedrive` |  |

### `FileValue` — OBJECT

| Field | Type | Deprecated |
|---|---|---|
| `column` | `Column!` |  |
| `files` | `[FileValueItem!]!` |  |
| `id` | `ID!` |  |
| `text` | `String` |  |
| `type` | `ColumnType!` |  |
| `value` | `JSON` |  |

### `FileValueItem` — UNION

A single file in a column.

### `FirstDayOfTheWeek` — ENUM

The first day of work week

| Enum value | Deprecated |
|---|---|
| `monday` |  |
| `sunday` |  |

### `Float` — SCALAR

The `Float` scalar type represents signed double-precision fractional values as specified by [IEEE 754](https://en.wikipedia.org/wiki/IEEE_floating_point).

### `Folder` — OBJECT

A workspace folder containing boards, docs, sub folders, etc.

| Field | Type | Deprecated |
|---|---|---|
| `children` | `[Board]!` |  |
| `color` | `FolderColor` |  |
| `created_at` | `Date!` |  |
| `custom_icon` | `FolderCustomIcon` |  |
| `font_weight` | `FolderFontWeight` |  |
| `id` | `ID!` |  |
| `name` | `String!` |  |
| `owner_id` | `ID` |  |
| `parent` | `Folder` |  |
| `sub_folders` | `[Folder]!` |  |
| `workspace` | `Workspace!` |  |

### `FolderColor` — ENUM

One value out of a list of valid folder colors

| Enum value | Deprecated |
|---|---|
| `AQUAMARINE` |  |
| `BRIGHT_BLUE` |  |
| `BRIGHT_GREEN` |  |
| `CHILI_BLUE` |  |
| `DARK_ORANGE` |  |
| `DARK_PURPLE` |  |
| `DARK_RED` |  |
| `DONE_GREEN` |  |
| `INDIGO` |  |
| `LIPSTICK` |  |
| `NULL` |  |
| `PURPLE` |  |
| `SOFIA_PINK` |  |
| `STUCK_RED` |  |
| `SUNSET` |  |
| `WORKING_ORANGE` |  |

### `FolderCustomIcon` — ENUM

One value out of a list of valid folder custom icons

| Enum value | Deprecated |
|---|---|
| `FOLDER` |  |
| `MOREBELOW` |  |
| `MOREBELOWFILLED` |  |
| `NULL` |  |
| `WORK` |  |

### `FolderFontWeight` — ENUM

One value out of a list of valid folder font weights

| Enum value | Deprecated |
|---|---|
| `FONT_WEIGHT_BOLD` |  |
| `FONT_WEIGHT_LIGHT` |  |
| `FONT_WEIGHT_NORMAL` |  |
| `FONT_WEIGHT_VERY_LIGHT` |  |
| `NULL` |  |

### `FormulaValue` — OBJECT

| Field | Type | Deprecated |
|---|---|---|
| `column` | `Column!` |  |
| `id` | `ID!` |  |
| `text` | `String` |  |
| `type` | `ColumnType!` |  |
| `value` | `JSON` |  |
| `display_value` | `String!` |  |

### `GrantMarketplaceAppDiscount` — OBJECT

| Field | Type | Deprecated |
|---|---|---|
| `days_valid` | `Int!` |  |
| `discount` | `Int!` |  |
| `is_recurring` | `Boolean!` |  |
| `period` | `DiscountPeriod` |  |
| `app_plan_ids` | `[String!]!` |  |
| `app_id` | `ID!` |  |

### `GrantMarketplaceAppDiscountData` — INPUT_OBJECT

| Input field | Type | Default |
|---|---|---|
| `days_valid` | `Int!` | `` |
| `discount` | `Int!` | `` |
| `is_recurring` | `Boolean!` | `` |
| `period` | `DiscountPeriod` | `` |
| `app_plan_ids` | `[!]!` | `` |

### `GrantMarketplaceAppDiscountResult` — OBJECT

| Field | Type | Deprecated |
|---|---|---|
| `granted_discount` | `GrantMarketplaceAppDiscount!` |  |

### `Group` — OBJECT

A group of items in a board.

| Field | Type | Deprecated |
|---|---|---|
| `archived` | `Boolean` |  |
| `color` | `String!` |  |
| `deleted` | `Boolean` |  |
| `id` | `ID!` |  |
| `items_page` | `ItemsResponse!` |  |
| `position` | `String!` |  |
| `title` | `String!` |  |

### `GroupAttributes` — ENUM

The group attributes available.

| Enum value | Deprecated |
|---|---|
| `color` |  |
| `position` |  |
| `relative_position_after` |  |
| `relative_position_before` |  |
| `title` |  |

### `GroupValue` — OBJECT

| Field | Type | Deprecated |
|---|---|---|
| `column` | `Column!` |  |
| `group` | `Group` |  |
| `group_id` | `ID` |  |
| `id` | `ID!` |  |
| `text` | `String` |  |
| `type` | `ColumnType!` |  |
| `value` | `JSON` |  |

### `HourValue` — OBJECT

| Field | Type | Deprecated |
|---|---|---|
| `column` | `Column!` |  |
| `hour` | `Int` |  |
| `id` | `ID!` |  |
| `minute` | `Int` |  |
| `text` | `String` |  |
| `type` | `ColumnType!` |  |
| `updated_at` | `Date` |  |
| `value` | `JSON` |  |

### `ID` — SCALAR

The `ID` scalar type represents a unique identifier, often used to refetch an object or as key for a cache. The ID type appears in a JSON response as a String; however, it is not intended to be human-readable. When expected as an input type, any string (such as `"4"`) or integer (such as `4`) input value will be accepted as an ID.

### `ISO8601DateTime` — SCALAR

An ISO 8601-encoded datetime (e.g., 2024-04-09T13:45:30Z)

### `Int` — SCALAR

The `Int` scalar type represents non-fractional signed whole numeric values. Int can represent values between -(2^31) and 2^31 - 1.

### `IntegrationValue` — OBJECT

| Field | Type | Deprecated |
|---|---|---|
| `column` | `Column!` |  |
| `entity_id` | `ID` |  |
| `id` | `ID!` |  |
| `issue_api_url` | `ID` |  |
| `issue_id` | `String` |  |
| `text` | `String` |  |
| `type` | `ColumnType!` |  |
| `value` | `JSON` |  |

### `InviteUsersError` — OBJECT

Error that occurred while inviting users

| Field | Type | Deprecated |
|---|---|---|
| `message` | `String` |  |
| `code` | `InviteUsersErrorCode` |  |
| `email` | `ID` |  |

### `InviteUsersErrorCode` — ENUM

Error codes that can occur while changing email domain.

| Enum value | Deprecated |
|---|---|
| `ERROR` |  |

### `InviteUsersResult` — OBJECT

Result of inviting users to the account.

| Field | Type | Deprecated |
|---|---|---|
| `invited_users` | `[User!]` |  |
| `errors` | `[InviteUsersError!]` |  |

### `Item` — OBJECT

An item (table row).

| Field | Type | Deprecated |
|---|---|---|
| `id` | `ID!` |  |
| `updates` | `[Update!]` |  |
| `assets` | `[Asset]` |  |
| `board` | `Board` |  |
| `column_values` | `[ColumnValue!]!` |  |
| `created_at` | `Date` |  |
| `creator` | `User` |  |
| `creator_id` | `String!` |  |
| `email` | `String!` |  |
| `group` | `Group` |  |
| `linked_items` | `[Item!]!` |  |
| `name` | `String!` |  |
| `parent_item` | `Item` |  |
| `relative_link` | `String` |  |
| `state` | `State` |  |
| `subitems` | `[Item]` |  |
| `subscribers` | `[User]!` |  |
| `updated_at` | `Date` |  |
| `url` | `String!` |  |

### `ItemIdValue` — OBJECT

| Field | Type | Deprecated |
|---|---|---|
| `column` | `Column!` |  |
| `id` | `ID!` |  |
| `item_id` | `ID!` |  |
| `text` | `String` |  |
| `type` | `ColumnType!` |  |
| `value` | `JSON` |  |

### `ItemsOrderByDirection` — ENUM

Sort direction

| Enum value | Deprecated |
|---|---|
| `asc` |  |
| `desc` |  |

### `ItemsPageByColumnValuesQuery` — INPUT_OBJECT

| Input field | Type | Default |
|---|---|---|
| `column_id` | `String!` | `` |
| `column_values` | `[String]!` | `` |

### `ItemsQuery` — INPUT_OBJECT

| Input field | Type | Default |
|---|---|---|
| `groups` | `[ItemsQueryGroup!]` | `` |
| `ids` | `[ID!]` | `` |
| `operator` | `ItemsQueryOperator` | `and` |
| `order_by` | `[ItemsQueryOrderBy!]` | `` |
| `rules` | `[ItemsQueryRule!]` | `` |

### `ItemsQueryGroup` — INPUT_OBJECT

A group of rules or rule groups

| Input field | Type | Default |
|---|---|---|
| `rules` | `[ItemsQueryRule!]` | `` |
| `groups` | `[ItemsQueryGroup!]` | `` |
| `operator` | `ItemsQueryOperator` | `and` |

### `ItemsQueryOperator` — ENUM

Logical operator

| Enum value | Deprecated |
|---|---|
| `or` |  |
| `and` |  |

### `ItemsQueryOrderBy` — INPUT_OBJECT

Sort the results by specified columns

| Input field | Type | Default |
|---|---|---|
| `column_id` | `String!` | `` |
| `direction` | `ItemsOrderByDirection` | `asc` |

### `ItemsQueryRule` — INPUT_OBJECT

A rule to filter items by a specific column

| Input field | Type | Default |
|---|---|---|
| `column_id` | `ID!` | `` |
| `compare_value` | `CompareValue!` | `` |
| `compare_attribute` | `String` | `` |
| `operator` | `ItemsQueryRuleOperator` | `any_of` |

### `ItemsQueryRuleOperator` — ENUM

Rule operator

| Enum value | Deprecated |
|---|---|
| `any_of` |  |
| `not_any_of` |  |
| `is_empty` |  |
| `is_not_empty` |  |
| `greater_than` |  |
| `greater_than_or_equals` |  |
| `lower_than` |  |
| `lower_than_or_equal` |  |
| `between` |  |
| `not_contains_text` |  |
| `contains_text` |  |
| `contains_terms` |  |
| `starts_with` |  |
| `ends_with` |  |
| `within_the_next` |  |
| `within_the_last` |  |

### `ItemsResponse` — OBJECT

| Field | Type | Deprecated |
|---|---|---|
| `cursor` | `String` |  |
| `items` | `[Item!]!` |  |

### `JSON` — SCALAR

A JSON formatted string.

### `Kind` — ENUM

Kind of assignee

| Enum value | Deprecated |
|---|---|
| `person` |  |
| `team` |  |

### `LastUpdatedValue` — OBJECT

| Field | Type | Deprecated |
|---|---|---|
| `column` | `Column!` |  |
| `id` | `ID!` |  |
| `text` | `String` |  |
| `type` | `ColumnType!` |  |
| `updated_at` | `Date` |  |
| `updater` | `User` |  |
| `updater_id` | `ID` |  |
| `value` | `JSON` |  |

### `Like` — OBJECT

| Field | Type | Deprecated |
|---|---|---|
| `id` | `ID!` |  |
| `creator_id` | `String` |  |
| `creator` | `User` |  |
| `reaction_type` | `String` |  |
| `created_at` | `Date` |  |
| `updated_at` | `Date` |  |

### `LinkValue` — OBJECT

| Field | Type | Deprecated |
|---|---|---|
| `column` | `Column!` |  |
| `id` | `ID!` |  |
| `text` | `String` |  |
| `type` | `ColumnType!` |  |
| `updated_at` | `Date` |  |
| `url` | `String` |  |
| `url_text` | `String` |  |
| `value` | `JSON` |  |

### `LocationValue` — OBJECT

| Field | Type | Deprecated |
|---|---|---|
| `address` | `String` |  |
| `city` | `String` |  |
| `city_short` | `String` |  |
| `column` | `Column!` |  |
| `country` | `String` |  |
| `country_short` | `String` |  |
| `id` | `ID!` |  |
| `lat` | `Float` |  |
| `lng` | `Float` |  |
| `place_id` | `String` |  |
| `street` | `String` |  |
| `street_number` | `String` |  |
| `street_number_short` | `String` |  |
| `street_short` | `String` |  |
| `text` | `String` |  |
| `type` | `ColumnType!` |  |
| `updated_at` | `Date` |  |
| `value` | `JSON` |  |

### `LongTextValue` — OBJECT

| Field | Type | Deprecated |
|---|---|---|
| `column` | `Column!` |  |
| `id` | `ID!` |  |
| `text` | `String` |  |
| `type` | `ColumnType!` |  |
| `updated_at` | `Date` |  |
| `value` | `JSON` |  |

### `ManagedColumn` — OBJECT

| Field | Type | Deprecated |
|---|---|---|
| `id` | `String` |  |
| `title` | `String` |  |
| `description` | `String` |  |
| `settings_json` | `JSON` |  |
| `created_by` | `ID` |  |
| `updated_by` | `ID` |  |
| `revision` | `Int` |  |
| `state` | `ManagedColumnState` |  |
| `created_at` | `Date` |  |
| `updated_at` | `Date` |  |
| `settings` | `ColumnSettings` |  |

### `ManagedColumnState` — ENUM

| Enum value | Deprecated |
|---|---|
| `active` |  |
| `deleted` |  |
| `inactive` |  |

### `ManagedColumnTypes` — ENUM

| Enum value | Deprecated |
|---|---|
| `status` |  |
| `dropdown` |  |

### `MarketplaceAppDiscount` — OBJECT

| Field | Type | Deprecated |
|---|---|---|
| `account_slug` | `String!` |  |
| `account_id` | `ID!` |  |
| `discount` | `Int!` |  |
| `is_recurring` | `Boolean!` |  |
| `app_plan_ids` | `[String!]!` |  |
| `period` | `DiscountPeriod` |  |
| `valid_until` | `String!` |  |
| `created_at` | `String!` |  |

### `MetadataInput` — INPUT_OBJECT

Metadata wrapper containing payload information for dependency configuration

| Input field | Type | Default |
|---|---|---|
| `payload` | `PayloadInput` | `` |

### `MirrorValue` — OBJECT

| Field | Type | Deprecated |
|---|---|---|
| `column` | `Column!` |  |
| `display_value` | `String!` |  |
| `id` | `ID!` |  |
| `mirrored_items` | `[MirroredItem!]!` |  |
| `text` | `String` |  |
| `type` | `ColumnType!` |  |
| `value` | `JSON` |  |

### `MirroredItem` — OBJECT

| Field | Type | Deprecated |
|---|---|---|
| `linked_board` | `Board!` |  |
| `linked_board_id` | `ID!` |  |
| `linked_item` | `Item!` |  |
| `mirrored_value` | `MirroredValue` |  |

### `MirroredValue` — UNION

Represents a mirrored value (column value, group, or board).

### `Mutation` — OBJECT

Root mutation type for the Dependencies service

| Field | Type | Deprecated |
|---|---|---|
| `like_update` | `Update` |  |
| `unlike_update` | `Update!` |  |
| `delete_update` | `Update` |  |
| `edit_update` | `Update!` |  |
| `pin_to_top` | `Update!` |  |
| `unpin_from_top` | `Update!` |  |
| `create_update` | `Update` |  |
| `create_timeline_item` | `TimelineItem` |  |
| `delete_timeline_item` | `TimelineItem` |  |
| `create_custom_activity` | `CustomActivity` |  |
| `delete_custom_activity` | `CustomActivity` |  |
| `create_dropdown_managed_column` | `DropdownManagedColumn` |  |
| `create_status_managed_column` | `StatusManagedColumn` |  |
| `update_dropdown_managed_column` | `DropdownManagedColumn` |  |
| `update_status_managed_column` | `StatusManagedColumn` |  |
| `activate_managed_column` | `ManagedColumn` |  |
| `deactivate_managed_column` | `ManagedColumn` |  |
| `delete_managed_column` | `ManagedColumn` |  |
| `delete_column` | `Column` |  |
| `create_column` | `Column` |  |
| `update_dependency_column` | `JSON!` |  |
| `batch_update_dependency_column` | `JSON!` |  |
| `export_markdown_from_doc` | `ExportMarkdownResult` | Please use the query export_markdown_from_doc instead. |
| `update_article_block` | `ArticleBlock` |  |
| `delete_marketplace_app_discount` | `DeleteMarketplaceAppDiscountResult!` |  |
| `grant_marketplace_app_discount` | `GrantMarketplaceAppDiscountResult!` |  |
| `add_file_to_column` | `Asset` |  |
| `add_file_to_update` | `Asset` |  |
| `add_subscribers_to_board` | `[User]` | use add_users_to_board instead |
| `add_teams_to_board` | `[Team]` |  |
| `add_teams_to_workspace` | `[Team]` |  |
| `add_users_to_board` | `[User]` |  |
| `add_users_to_team` | `ChangeTeamMembershipsResult` |  |
| `add_users_to_workspace` | `[User]` |  |
| `archive_board` | `Board` |  |
| `archive_group` | `Group` |  |
| `archive_item` | `Item` |  |
| `batch_extend_trial_period` | `BatchExtendTrialPeriod` |  |
| `change_column_metadata` | `Column` |  |
| `change_column_title` | `Column` |  |
| `change_column_value` | `Item` |  |
| `change_multiple_column_values` | `Item` |  |
| `change_simple_column_value` | `Item` |  |
| `clear_item_updates` | `Item` |  |
| `complexity` | `Complexity` |  |
| `create_board` | `Board` |  |
| `create_doc` | `Document` |  |
| `create_doc_block` | `DocumentBlock` |  |
| `create_folder` | `Folder` |  |
| `create_group` | `Group` |  |
| `create_item` | `Item` |  |
| `create_notification` | `Notification` |  |
| `create_or_get_tag` | `Tag` |  |
| `create_subitem` | `Item` |  |
| `create_webhook` | `Webhook` |  |
| `create_workspace` | `Workspace` |  |
| `delete_board` | `Board` |  |
| `delete_doc_block` | `DocumentBlockIdOnly` |  |
| `delete_folder` | `Folder` |  |
| `delete_group` | `Group` |  |
| `delete_item` | `Item` |  |
| `delete_subscribers_from_board` | `[User]` |  |
| `delete_teams_from_board` | `[Team]` |  |
| `delete_teams_from_workspace` | `[Team]` |  |
| `delete_users_from_workspace` | `[User]` |  |
| `delete_webhook` | `Webhook` |  |
| `delete_workspace` | `Workspace` |  |
| `duplicate_board` | `BoardDuplication` |  |
| `duplicate_group` | `Group` |  |
| `duplicate_item` | `Item` |  |
| `increase_app_subscription_operations` | `AppSubscriptionOperationsCounter` |  |
| `move_item_to_board` | `Item` |  |
| `move_item_to_group` | `Item` |  |
| `remove_mock_app_subscription` | `AppSubscription` |  |
| `remove_users_from_team` | `ChangeTeamMembershipsResult` |  |
| `set_mock_app_subscription` | `AppSubscription` |  |
| `update_assets_on_item` | `Item` |  |
| `update_board` | `JSON` |  |
| `update_doc_block` | `DocumentBlock` |  |
| `update_folder` | `Folder` |  |
| `update_group` | `Group` |  |
| `update_workspace` | `Workspace` |  |
| `use_template` | `Template` |  |
| `create_team` | `Team` |  |
| `activate_users` | `ActivateUsersResult` |  |
| `deactivate_users` | `DeactivateUsersResult` |  |
| `delete_team` | `Team` |  |
| `update_users_role` | `UpdateUsersRoleResult` |  |
| `assign_team_owners` | `AssignTeamOwnersResult` |  |
| `remove_team_owners` | `RemoveTeamOwnersResult` |  |
| `update_email_domain` | `UpdateEmailDomainResult` |  |
| `update_multiple_users` | `UpdateUserAttributesResult` |  |
| `invite_users` | `InviteUsersResult` |  |

### `Notification` — OBJECT

A notification.

| Field | Type | Deprecated |
|---|---|---|
| `id` | `ID!` |  |
| `text` | `String` |  |

### `NotificationTargetType` — ENUM

The notification's target type.

| Enum value | Deprecated |
|---|---|
| `Post` |  |
| `Project` |  |

### `NumberValueUnitDirection` — ENUM

Indicates where the unit symbol should be placed in a number value

| Enum value | Deprecated |
|---|---|
| `left` |  |
| `right` |  |

### `NumbersValue` — OBJECT

| Field | Type | Deprecated |
|---|---|---|
| `column` | `Column!` |  |
| `direction` | `NumberValueUnitDirection` |  |
| `id` | `ID!` |  |
| `number` | `Float` |  |
| `symbol` | `String` |  |
| `text` | `String` |  |
| `type` | `ColumnType!` |  |
| `value` | `JSON` |  |

### `OutOfOffice` — OBJECT

The working status of a user.

| Field | Type | Deprecated |
|---|---|---|
| `active` | `Boolean` |  |
| `disable_notifications` | `Boolean` |  |
| `end_date` | `Date` |  |
| `start_date` | `Date` |  |
| `type` | `String` |  |

### `PaginationInput` — INPUT_OBJECT

Pagination parameters for queries

| Input field | Type | Default |
|---|---|---|
| `limit` | `Int` | `` |
| `lastId` | `Int` | `` |

### `PayloadInput` — INPUT_OBJECT

Input type for dependency metadata payload containing dependency type and lag configuration

| Input field | Type | Default |
|---|---|---|
| `dependency_type` | `DependencyRelation` | `` |
| `lag` | `Int` | `` |

### `PeopleEntity` — OBJECT

| Field | Type | Deprecated |
|---|---|---|
| `id` | `ID!` |  |
| `kind` | `Kind` |  |

### `PeopleValue` — OBJECT

| Field | Type | Deprecated |
|---|---|---|
| `column` | `Column!` |  |
| `id` | `ID!` |  |
| `persons_and_teams` | `[PeopleEntity!]` |  |
| `text` | `String` |  |
| `type` | `ColumnType!` |  |
| `updated_at` | `Date` |  |
| `value` | `JSON` |  |

### `PersonValue` — OBJECT

| Field | Type | Deprecated |
|---|---|---|
| `column` | `Column!` |  |
| `id` | `ID!` |  |
| `person_id` | `ID` |  |
| `text` | `String` |  |
| `type` | `ColumnType!` |  |
| `updated_at` | `Date` |  |
| `value` | `JSON` |  |

### `PhoneValue` — OBJECT

| Field | Type | Deprecated |
|---|---|---|
| `column` | `Column!` |  |
| `country_short_name` | `String` |  |
| `id` | `ID!` |  |
| `phone` | `String` |  |
| `text` | `String` |  |
| `type` | `ColumnType!` |  |
| `updated_at` | `Date` |  |
| `value` | `JSON` |  |

### `Plan` — OBJECT

A payment plan.

| Field | Type | Deprecated |
|---|---|---|
| `max_users` | `Int!` |  |
| `period` | `String` |  |
| `tier` | `String` |  |
| `version` | `Int!` |  |

### `PlatformApi` — OBJECT

The Platform API's data.

| Field | Type | Deprecated |
|---|---|---|
| `daily_limit` | `DailyLimit` |  |
| `daily_analytics` | `DailyAnalytics` |  |

### `PlatformApiDailyAnalyticsByApp` — OBJECT

API usage per app.

| Field | Type | Deprecated |
|---|---|---|
| `app` | `AppType` |  |
| `usage` | `Int!` |  |
| `api_app_id` | `ID!` |  |

### `PlatformApiDailyAnalyticsByDay` — OBJECT

API usage per day.

| Field | Type | Deprecated |
|---|---|---|
| `day` | `String!` |  |
| `usage` | `Int!` |  |

### `PlatformApiDailyAnalyticsByUser` — OBJECT

API usage per user.

| Field | Type | Deprecated |
|---|---|---|
| `user` | `User` |  |
| `usage` | `Int!` |  |

### `PositionRelative` — ENUM

The position relative method.

| Enum value | Deprecated |
|---|---|
| `after_at` |  |
| `before_at` |  |

### `Product` — ENUM

The product to invite the users to.

| Enum value | Deprecated |
|---|---|
| `work_management` |  |
| `crm` |  |
| `dev` |  |
| `service` |  |
| `whiteboard` |  |
| `knowledge` |  |
| `forms` |  |
| `workflows` |  |

### `ProgressValue` — OBJECT

| Field | Type | Deprecated |
|---|---|---|
| `column` | `Column!` |  |
| `id` | `ID!` |  |
| `text` | `String` |  |
| `type` | `ColumnType!` |  |
| `value` | `JSON` |  |

### `Query` — OBJECT

Root query type for the Dependencies service

| Field | Type | Deprecated |
|---|---|---|
| `connections` | `[Connection!]` |  |
| `user_connections` | `[Connection!]` |  |
| `account_connections` | `[Connection!]` |  |
| `connection` | `Connection` |  |
| `connection_board_ids` | `[Int!]` |  |
| `trigger_events` | `TriggerEventsPage` |  |
| `trigger_event` | `TriggerEvent` |  |
| `block_events` | `BlockEventsPage` |  |
| `account_trigger_statistics` | `AccountTriggerStatistics` |  |
| `account_triggers_statistics_by_entity_id` | `AccountTriggersByEntityId` |  |
| `empty` | `String` |  |
| `updates` | `[Update!]` |  |
| `custom_activity` | `[CustomActivity!]` |  |
| `timeline_item` | `TimelineItem` |  |
| `timeline` | `TimelineResponse` |  |
| `managed_column` | `[ManagedColumn!]` |  |
| `export_graph` | `BoardGraphExport` |  |
| `dependency_column_config` | `DependencyColumnConfigResult` |  |
| `export_events` | `EventsExport` |  |
| `marketplace_app_discounts` | `[MarketplaceAppDiscount!]!` |  |
| `app_subscriptions` | `AppSubscriptions!` |  |
| `app` | `AppType` |  |
| `account` | `Account` |  |
| `app_installs` | `[AppInstall]` |  |
| `app_subscription` | `[AppSubscription]` |  |
| `app_subscription_operations` | `AppSubscriptionOperationsCounter` |  |
| `apps_monetization_info` | `AppsMonetizationInfo` |  |
| `apps_monetization_status` | `AppMonetizationStatus` |  |
| `assets` | `[Asset]` |  |
| `boards` | `[Board]` |  |
| `complexity` | `Complexity` |  |
| `docs` | `[Document]` |  |
| `folders` | `[Folder]` |  |
| `items` | `[Item]` |  |
| `items_page_by_column_values` | `ItemsResponse!` |  |
| `me` | `User` |  |
| `next_items_page` | `ItemsResponse!` |  |
| `tags` | `[Tag]` |  |
| `teams` | `[Team]` |  |
| `users` | `[User]` |  |
| `webhooks` | `[Webhook]` |  |
| `workspaces` | `[Workspace]` |  |
| `board_candidates` | `[Board!]` |  |
| `version` | `Version!` |  |
| `versions` | `[Version!]` |  |
| `platform_api` | `PlatformApi` |  |
| `sprints` | `[Sprint!]` |  |
| `account_roles` | `[AccountRole!]` |  |

### `RatingValue` — OBJECT

| Field | Type | Deprecated |
|---|---|---|
| `column` | `Column!` |  |
| `id` | `ID!` |  |
| `rating` | `Int` |  |
| `text` | `String` |  |
| `type` | `ColumnType!` |  |
| `updated_at` | `Date` |  |
| `value` | `JSON` |  |

### `RemoveTeamOwnersError` — OBJECT

Error that occurred while removing team owners.

| Field | Type | Deprecated |
|---|---|---|
| `message` | `String` |  |
| `code` | `RemoveTeamOwnersErrorCode` |  |
| `user_id` | `ID` |  |

### `RemoveTeamOwnersErrorCode` — ENUM

Error codes that can occur while removing team owners.

| Enum value | Deprecated |
|---|---|
| `VIEWERS_OR_GUESTS` |  |
| `USER_NOT_MEMBER_OF_TEAM` |  |
| `EXCEEDS_BATCH_LIMIT` |  |
| `INVALID_INPUT` |  |
| `USER_NOT_FOUND` |  |
| `CANNOT_UPDATE_SELF` |  |
| `FAILED` |  |

### `RemoveTeamOwnersResult` — OBJECT

Result of removing the team's ownership.

| Field | Type | Deprecated |
|---|---|---|
| `team` | `Team` |  |
| `errors` | `[RemoveTeamOwnersError!]` |  |

### `Reply` — OBJECT

A reply for an update.

| Field | Type | Deprecated |
|---|---|---|
| `id` | `ID!` |  |
| `body` | `String!` |  |
| `kind` | `String!` |  |
| `creator_id` | `String` |  |
| `edited_at` | `Date!` |  |
| `creator` | `User` |  |
| `likes` | `[Like!]!` |  |
| `pinned_to_top` | `[UpdatePin!]!` |  |
| `viewers` | `[Watcher!]!` |  |
| `created_at` | `Date` |  |
| `updated_at` | `Date` |  |
| `text_body` | `String` |  |

### `Sprint` — OBJECT

A monday dev sprint.

| Field | Type | Deprecated |
|---|---|---|
| `id` | `ID!` |  |
| `name` | `String` |  |
| `items` | `[Item!]` |  |
| `start_date` | `Date` |  |
| `end_date` | `Date` |  |
| `timeline` | `SprintTimeline` |  |
| `state` | `SprintState` |  |
| `snapshots` | `[SprintSnapshot!]` |  |

### `SprintSnapshot` — OBJECT

A monday dev sprint snapshot.

| Field | Type | Deprecated |
|---|---|---|
| `id` | `ID` |  |
| `type` | `SprintSnapshotKind` |  |
| `items` | `[SprintSnapshotItem!]` |  |
| `columns_metadata` | `[SprintSnapshotColumnMetadata!]` |  |
| `sprint_id` | `ID` |  |
| `created_at` | `Date` |  |
| `updated_at` | `Date` |  |

### `SprintSnapshotColumnMetadata` — OBJECT

A monday dev sprint snapshot column metadata.

| Field | Type | Deprecated |
|---|---|---|
| `id` | `String!` |  |
| `done_status_indexes` | `[Int!]!` |  |

### `SprintSnapshotItem` — OBJECT

A monday dev sprint snapshot item.

| Field | Type | Deprecated |
|---|---|---|
| `id` | `ID!` |  |
| `column_values` | `[SprintSnapshotItemColumnValue!]` |  |

### `SprintSnapshotItemColumnValue` — OBJECT

A monday dev sprint snapshot item column value.

| Field | Type | Deprecated |
|---|---|---|
| `id` | `String!` |  |
| `type` | `String!` |  |
| `value` | `JSON` |  |

### `SprintSnapshotKind` — ENUM

The kind of sprint snapshot.

| Enum value | Deprecated |
|---|---|
| `START` |  |
| `COMPLETE` |  |

### `SprintState` — ENUM

current state of the monday dev sprint.

| Enum value | Deprecated |
|---|---|
| `PLANNED` |  |
| `ACTIVE` |  |
| `COMPLETED` |  |

### `SprintTimeline` — OBJECT

user-editable planned timeline for the monday dev sprint, which may differ from its start and complete dates

| Field | Type | Deprecated |
|---|---|---|
| `from` | `Date` |  |
| `to` | `Date` |  |

### `State` — ENUM

The possible states for a board or item.

| Enum value | Deprecated |
|---|---|
| `active` |  |
| `all` |  |
| `archived` |  |
| `deleted` |  |

### `StatusColumnColors` — ENUM

| Enum value | Deprecated |
|---|---|
| `working_orange` |  |
| `done_green` |  |
| `stuck_red` |  |
| `dark_blue` |  |
| `purple` |  |
| `explosive` |  |
| `grass_green` |  |
| `bright_blue` |  |
| `saladish` |  |
| `egg_yolk` |  |
| `blackish` |  |
| `dark_red` |  |
| `sofia_pink` |  |
| `lipstick` |  |
| `dark_purple` |  |
| `bright_green` |  |
| `chili_blue` |  |
| `american_gray` |  |
| `brown` |  |
| `dark_orange` |  |
| `sunset` |  |
| `bubble` |  |
| `peach` |  |
| `berry` |  |
| `winter` |  |
| `river` |  |
| `navy` |  |
| `aquamarine` |  |
| `indigo` |  |
| `dark_indigo` |  |
| `pecan` |  |
| `lavender` |  |
| `royal` |  |
| `steel` |  |
| `orchid` |  |
| `lilac` |  |
| `tan` |  |
| `sky` |  |
| `coffee` |  |
| `teal` |  |

### `StatusColumnSettings` — OBJECT

| Field | Type | Deprecated |
|---|---|---|
| `type` | `ManagedColumnTypes` |  |
| `labels` | `[StatusLabel!]` |  |

### `StatusLabel` — OBJECT

| Field | Type | Deprecated |
|---|---|---|
| `id` | `Int` |  |
| `label` | `String` |  |
| `color` | `StatusColumnColors` |  |
| `index` | `Int` |  |
| `description` | `String` |  |
| `is_deactivated` | `Boolean` |  |
| `is_done` | `Boolean` |  |

### `StatusLabelStyle` — OBJECT

A status label style.

| Field | Type | Deprecated |
|---|---|---|
| `border` | `String!` |  |
| `color` | `String!` |  |

### `StatusManagedColumn` — OBJECT

| Field | Type | Deprecated |
|---|---|---|
| `id` | `String` |  |
| `title` | `String` |  |
| `description` | `String` |  |
| `settings_json` | `JSON` |  |
| `created_by` | `ID` |  |
| `updated_by` | `ID` |  |
| `revision` | `Int` |  |
| `state` | `ManagedColumnState` |  |
| `created_at` | `Date` |  |
| `updated_at` | `Date` |  |
| `settings` | `StatusColumnSettings` |  |

### `StatusValue` — OBJECT

| Field | Type | Deprecated |
|---|---|---|
| `column` | `Column!` |  |
| `id` | `ID!` |  |
| `index` | `Int` |  |
| `is_done` | `Boolean` |  |
| `label` | `String` |  |
| `label_style` | `StatusLabelStyle` |  |
| `text` | `String` |  |
| `type` | `ColumnType!` |  |
| `update_id` | `ID` |  |
| `updated_at` | `Date` |  |
| `value` | `JSON` |  |

### `String` — SCALAR

The `String` scalar type represents textual data, represented as UTF-8 character sequences. The String type is most often used by GraphQL to represent free-form human-readable text.

### `SubscriptionDiscount` — OBJECT

The discounts granted to the subscription

| Field | Type | Deprecated |
|---|---|---|
| `value` | `Int!` |  |
| `discount_model_type` | `SubscriptionDiscountModelType!` |  |
| `discount_type` | `SubscriptionDiscountType!` |  |

### `SubscriptionDiscountModelType` — ENUM

The information whether the discount is percentage or nominal

| Enum value | Deprecated |
|---|---|
| `percent` |  |
| `nominal` |  |

### `SubscriptionDiscountType` — ENUM

The information whether the discount has been granted one time or recurring

| Enum value | Deprecated |
|---|---|
| `recurring` |  |
| `one_time` |  |

### `SubscriptionPeriodType` — ENUM

The billing period of the subscription. Possible values: monthly, yearly

| Enum value | Deprecated |
|---|---|
| `monthly` |  |
| `yearly` |  |

### `SubscriptionStatus` — ENUM

The status of the subscription. Possible values: active, inactive.

| Enum value | Deprecated |
|---|---|
| `active` |  |
| `inactive` |  |

### `SubtasksValue` — OBJECT

| Field | Type | Deprecated |
|---|---|---|
| `column` | `Column!` |  |
| `display_value` | `String!` |  |
| `id` | `ID!` |  |
| `subitems` | `[Item!]!` |  |
| `subitems_ids` | `[ID!]!` |  |
| `text` | `String` |  |
| `type` | `ColumnType!` |  |
| `value` | `JSON` |  |

### `Tag` — OBJECT

A tag

| Field | Type | Deprecated |
|---|---|---|
| `color` | `String!` |  |
| `id` | `ID!` |  |
| `name` | `String!` |  |

### `TagsValue` — OBJECT

| Field | Type | Deprecated |
|---|---|---|
| `column` | `Column!` |  |
| `id` | `ID!` |  |
| `tag_ids` | `[Int!]!` |  |
| `tags` | `[Tag!]!` |  |
| `text` | `String` |  |
| `type` | `ColumnType!` |  |
| `value` | `JSON` |  |

### `Team` — OBJECT

A team of users.

| Field | Type | Deprecated |
|---|---|---|
| `id` | `ID!` |  |
| `owners` | `[User!]!` |  |
| `picture_url` | `String` |  |
| `users` | `[User]` |  |
| `name` | `String!` |  |
| `is_guest` | `Boolean` |  |

### `TeamValue` — OBJECT

| Field | Type | Deprecated |
|---|---|---|
| `column` | `Column!` |  |
| `id` | `ID!` |  |
| `team_id` | `Int` |  |
| `text` | `String` |  |
| `type` | `ColumnType!` |  |
| `updated_at` | `Date` |  |
| `value` | `JSON` |  |

### `Template` — OBJECT

A monday.com template.

| Field | Type | Deprecated |
|---|---|---|
| `process_id` | `String` |  |

### `TextValue` — OBJECT

| Field | Type | Deprecated |
|---|---|---|
| `column` | `Column!` |  |
| `id` | `ID!` |  |
| `text` | `String` |  |
| `type` | `ColumnType!` |  |
| `value` | `JSON` |  |

### `TimeTrackingHistoryItem` — OBJECT

| Field | Type | Deprecated |
|---|---|---|
| `created_at` | `Date!` |  |
| `ended_at` | `Date` |  |
| `ended_user_id` | `ID` |  |
| `id` | `ID!` |  |
| `manually_entered_end_date` | `Boolean!` |  |
| `manually_entered_end_time` | `Boolean!` |  |
| `manually_entered_start_date` | `Boolean!` |  |
| `manually_entered_start_time` | `Boolean!` |  |
| `started_at` | `Date` |  |
| `started_user_id` | `ID` |  |
| `status` | `String!` |  |
| `updated_at` | `Date` |  |

### `TimeTrackingValue` — OBJECT

| Field | Type | Deprecated |
|---|---|---|
| `column` | `Column!` |  |
| `duration` | `Int` |  |
| `history` | `[TimeTrackingHistoryItem!]!` |  |
| `id` | `ID!` |  |
| `running` | `Boolean` |  |
| `started_at` | `Date` |  |
| `text` | `String` |  |
| `type` | `ColumnType!` |  |
| `updated_at` | `Date` |  |
| `value` | `JSON` |  |

### `TimelineDateInput` — INPUT_OBJECT

Input type for timeline dates with from and to date strings

| Input field | Type | Default |
|---|---|---|
| `id` | `ID!` | `` |
| `from` | `String!` | `` |
| `to` | `String!` | `` |

### `TimelineItem` — OBJECT

| Field | Type | Deprecated |
|---|---|---|
| `id` | `ID` |  |
| `type` | `String` |  |
| `item` | `Item` |  |
| `board` | `Board` |  |
| `user` | `User` |  |
| `title` | `String` |  |
| `custom_activity_id` | `String` |  |
| `content` | `String` |  |
| `created_at` | `Date!` |  |

### `TimelineItemTimeRange` — INPUT_OBJECT

| Input field | Type | Default |
|---|---|---|
| `start_timestamp` | `ISO8601DateTime!` | `` |
| `end_timestamp` | `ISO8601DateTime!` | `` |

### `TimelineItemsPage` — OBJECT

| Field | Type | Deprecated |
|---|---|---|
| `timeline_items` | `[TimelineItem!]!` |  |
| `cursor` | `String` |  |

### `TimelineResponse` — OBJECT

| Field | Type | Deprecated |
|---|---|---|
| `timeline_items_page` | `TimelineItemsPage!` |  |

### `TimelineValue` — OBJECT

| Field | Type | Deprecated |
|---|---|---|
| `column` | `Column!` |  |
| `from` | `Date` |  |
| `id` | `ID!` |  |
| `text` | `String` |  |
| `to` | `Date` |  |
| `type` | `ColumnType!` |  |
| `updated_at` | `Date` |  |
| `value` | `JSON` |  |
| `visualization_type` | `String` |  |

### `TriggerEvent` — OBJECT

Represents a single automation trigger event

| Field | Type | Deprecated |
|---|---|---|
| `accountId` | `Int` |  |
| `triggerUuid` | `String` |  |
| `eventKind` | `String` |  |
| `eventState` | `String` |  |
| `triggerStarted` | `Float` |  |
| `triggerStartedAt` | `ISO8601DateTime` |  |
| `createdAt` | `ISO8601DateTime` |  |
| `errorReason` | `String` |  |
| `billingActionsCount` | `Int` |  |
| `waitingForTriggerName` | `String` |  |
| `triggerDuration` | `Float` |  |
| `entityKind` | `String` |  |
| `reignitionSubscriptionId` | `String` |  |
| `hostType` | `String` |  |
| `hostInstanceId` | `String` |  |
| `creatorAppFeatureReferenceId` | `String` |  |

### `TriggerEventState` — ENUM

Automation run status

| Enum value | Deprecated |
|---|---|
| `success` |  |
| `failure` |  |
| `exhausted` |  |

### `TriggerEventsFiltersInput` — INPUT_OBJECT

Filters for querying trigger events

| Input field | Type | Default |
|---|---|---|
| `dateRange` | `DateRangeInput` | `` |
| `entityKind` | `String` | `` |
| `automationIds` | `[Int!]` | `` |
| `workflowEntityIds` | `[Int!]` | `` |
| `stateFilter` | `[String!]` | `` |
| `itemId` | `String` | `` |
| `filterByEntity` | `Boolean` | `` |
| `isAutomationsEntity` | `Boolean` | `` |
| `appFilter` | `[String!]` | `` |
| `hostType` | `String` | `` |
| `hostInstanceId` | `String` | `` |
| `creatorAppFeatureReferenceId` | `Int` | `` |
| `billingActionCountField` | `String` | `` |
| `isWorkflowFilter` | `Boolean` | `` |
| `boardId` | `String` | `` |
| `statusFilter` | `[String!]` | `` |

### `TriggerEventsPage` — OBJECT

A page of trigger events and pagination data

| Field | Type | Deprecated |
|---|---|---|
| `triggerEvents` | `[TriggerEvent!]` |  |

### `UnsupportedValue` — OBJECT

| Field | Type | Deprecated |
|---|---|---|
| `column` | `Column!` |  |
| `id` | `ID!` |  |
| `text` | `String` |  |
| `type` | `ColumnType!` |  |
| `value` | `JSON` |  |

### `Update` — OBJECT

An update.

| Field | Type | Deprecated |
|---|---|---|
| `id` | `ID!` |  |
| `body` | `String!` |  |
| `creator_id` | `String` |  |
| `edited_at` | `Date!` |  |
| `creator` | `User` |  |
| `likes` | `[Like!]!` |  |
| `pinned_to_top` | `[UpdatePin!]!` |  |
| `viewers` | `[Watcher!]!` |  |
| `created_at` | `Date` |  |
| `updated_at` | `Date` |  |
| `item_id` | `String` |  |
| `item` | `Item` |  |
| `replies` | `[Reply!]` |  |
| `assets` | `[Asset]` |  |
| `text_body` | `String` |  |

### `UpdateDependencyColumnInput` — INPUT_OBJECT

Input type for updating a single dependency relationship between pulses

| Input field | Type | Default |
|---|---|---|
| `linkedPulseId` | `ID!` | `` |
| `metadata` | `MetadataInput` | `` |

### `UpdateDropdownColumnSettingsInput` — INPUT_OBJECT

| Input field | Type | Default |
|---|---|---|
| `labels` | `[!]!` | `` |
| `limit_select` | `Boolean` | `` |
| `label_limit_count` | `Int` | `` |

### `UpdateDropdownLabelInput` — INPUT_OBJECT

| Input field | Type | Default |
|---|---|---|
| `label` | `String!` | `` |
| `id` | `Int` | `` |
| `is_deactivated` | `Boolean` | `` |

### `UpdateEmailDomainAttributesInput` — INPUT_OBJECT

Attributes of the email domain to be updated.

| Input field | Type | Default |
|---|---|---|
| `user_ids` | `[!]!` | `` |
| `new_domain` | `String!` | `` |

### `UpdateEmailDomainError` — OBJECT

Error that occurred while changing email domain.

| Field | Type | Deprecated |
|---|---|---|
| `message` | `String` |  |
| `code` | `UpdateEmailDomainErrorCode` |  |
| `user_id` | `ID` |  |

### `UpdateEmailDomainErrorCode` — ENUM

Error codes that can occur while changing email domain.

| Enum value | Deprecated |
|---|---|
| `UPDATE_EMAIL_DOMAIN_ERROR` |  |
| `EXCEEDS_BATCH_LIMIT` |  |
| `INVALID_INPUT` |  |
| `USER_NOT_FOUND` |  |
| `CANNOT_UPDATE_SELF` |  |
| `FAILED` |  |

### `UpdateEmailDomainResult` — OBJECT

Result of updating the email domain for the specified users.

| Field | Type | Deprecated |
|---|---|---|
| `updated_users` | `[User!]` |  |
| `errors` | `[UpdateEmailDomainError!]` |  |

### `UpdatePin` — OBJECT

The pin to top data of the update.

| Field | Type | Deprecated |
|---|---|---|
| `item_id` | `ID!` |  |

### `UpdateStatusColumnSettingsInput` — INPUT_OBJECT

| Input field | Type | Default |
|---|---|---|
| `labels` | `[!]!` | `` |

### `UpdateStatusLabelInput` — INPUT_OBJECT

| Input field | Type | Default |
|---|---|---|
| `label` | `String!` | `` |
| `color` | `StatusColumnColors!` | `` |
| `index` | `Int!` | `` |
| `description` | `String` | `` |
| `is_done` | `Boolean` | `` |
| `id` | `Int` | `` |
| `is_deactivated` | `Boolean` | `` |

### `UpdateUserAttributesError` — OBJECT

Error that occurred while updating users attributes.

| Field | Type | Deprecated |
|---|---|---|
| `message` | `String` |  |
| `code` | `UpdateUserAttributesErrorCode` |  |
| `user_id` | `ID` |  |

### `UpdateUserAttributesErrorCode` — ENUM

Error codes that can occur while updating user attributes.

| Enum value | Deprecated |
|---|---|
| `INVALID_FIELD` |  |

### `UpdateUserAttributesResult` — OBJECT

The result of updating users attributes.

| Field | Type | Deprecated |
|---|---|---|
| `updated_users` | `[User!]` |  |
| `errors` | `[UpdateUserAttributesError!]` |  |

### `UpdateUsersRoleError` — OBJECT

Error that occurred during updating users role.

| Field | Type | Deprecated |
|---|---|---|
| `message` | `String` |  |
| `code` | `UpdateUsersRoleErrorCode` |  |
| `user_id` | `ID` |  |

### `UpdateUsersRoleErrorCode` — ENUM

Error codes for updating users roles.

| Enum value | Deprecated |
|---|---|
| `EXCEEDS_BATCH_LIMIT` |  |
| `INVALID_INPUT` |  |
| `USER_NOT_FOUND` |  |
| `CANNOT_UPDATE_SELF` |  |
| `FAILED` |  |

### `UpdateUsersRoleResult` — OBJECT

Result of updating users role.

| Field | Type | Deprecated |
|---|---|---|
| `updated_users` | `[User!]` |  |
| `errors` | `[UpdateUsersRoleError!]` |  |

### `UpdateWorkspaceAttributesInput` — INPUT_OBJECT

Attributes of a workspace to update

| Input field | Type | Default |
|---|---|---|
| `description` | `String` | `` |
| `kind` | `WorkspaceKind` | `` |
| `name` | `String` | `` |

### `User` — OBJECT

A monday.com user.

| Field | Type | Deprecated |
|---|---|---|
| `id` | `ID!` |  |
| `account` | `Account!` |  |
| `account_products` | `[AccountProduct!]` |  |
| `birthday` | `Date` |  |
| `country_code` | `String` |  |
| `created_at` | `Date` |  |
| `current_language` | `String` |  |
| `custom_field_metas` | `[CustomFieldMetas]` |  |
| `custom_field_values` | `[CustomFieldValue]` |  |
| `email` | `String!` |  |
| `enabled` | `Boolean!` | This field is deprecated. Please use status instead. |
| `encrypt_api_token` | `String` | This field is deprecated and will be removed in later versions. |
| `is_admin` | `Boolean` | This field is deprecated. Please use kind instead. |
| `is_guest` | `Boolean` | This field is deprecated. Please use kind instead. |
| `is_pending` | `Boolean` | This field is deprecated. Please use status instead. |
| `is_verified` | `Boolean` | This field is deprecated. Please use is_email_confirmed instead. |
| `is_view_only` | `Boolean` | This field is deprecated. Please use kind instead. |
| `join_date` | `Date` | This field is deprecated. Please use became_active_at instead. |
| `last_activity` | `Date` |  |
| `location` | `String` |  |
| `mobile_phone` | `String` |  |
| `name` | `String!` |  |
| `out_of_office` | `OutOfOffice` |  |
| `phone` | `String` |  |
| `photo_original` | `String` | This field is deprecated. Please use photo_url.original instead. |
| `photo_small` | `String` | This field is deprecated. Please use photo_url.small instead. |
| `photo_thumb` | `String` | This field is deprecated. Please use photo_url.thumb instead. |
| `photo_thumb_small` | `String` | This field is deprecated. Please use photo_url.thumb_small instead. |
| `photo_tiny` | `String` | This field is deprecated. Please use photo_url.tiny instead. |
| `sign_up_product_kind` | `String` | This field is deprecated and will be removed in later versions. |
| `teams` | `[Team]` |  |
| `time_zone_identifier` | `String` |  |
| `title` | `String` |  |
| `url` | `String!` |  |
| `utc_hours_diff` | `Int` |  |

### `UserAttributesInput` — INPUT_OBJECT

The attributes to update for a user.

| Input field | Type | Default |
|---|---|---|
| `birthday` | `String` | `` |
| `email` | `String` | `` |
| `join_date` | `String` | `` |
| `name` | `String` | `` |
| `location` | `String` | `` |
| `mobile_phone` | `String` | `` |
| `phone` | `String` | `` |
| `title` | `String` | `` |
| `department` | `String` | `` |

### `UserKind` — ENUM

The possibilities for a user kind.

| Enum value | Deprecated |
|---|---|
| `all` |  |
| `guests` |  |
| `non_guests` |  |
| `non_pending` |  |

### `UserRole` — ENUM

The role of the user.

| Enum value | Deprecated |
|---|---|
| `GUEST` |  |
| `VIEW_ONLY` |  |
| `MEMBER` |  |
| `ADMIN` |  |

### `UserUpdateInput` — INPUT_OBJECT

| Input field | Type | Default |
|---|---|---|
| `user_id` | `ID!` | `` |
| `user_attribute_updates` | `UserAttributesInput!` | `` |

### `Version` — OBJECT

An object containing the API version details

| Field | Type | Deprecated |
|---|---|---|
| `display_name` | `String!` |  |
| `kind` | `VersionKind!` |  |
| `value` | `String!` |  |

### `VersionKind` — ENUM

All possible API version types

| Enum value | Deprecated |
|---|---|
| `current` |  |
| `deprecated` |  |
| `dev` |  |
| `maintenance` |  |
| `old__maintenance` |  |
| `old_previous_maintenance` |  |
| `previous_maintenance` |  |
| `release_candidate` |  |

### `VoteValue` — OBJECT

| Field | Type | Deprecated |
|---|---|---|
| `column` | `Column!` |  |
| `id` | `ID!` |  |
| `text` | `String` |  |
| `type` | `ColumnType!` |  |
| `updated_at` | `Date` |  |
| `value` | `JSON` |  |
| `vote_count` | `Int!` |  |
| `voter_ids` | `[ID!]!` |  |
| `voters` | `[User!]!` |  |

### `Watcher` — OBJECT

The viewer of the update.

| Field | Type | Deprecated |
|---|---|---|
| `user_id` | `ID!` |  |
| `medium` | `String!` |  |
| `user` | `User` |  |

### `Webhook` — OBJECT

Monday webhooks

| Field | Type | Deprecated |
|---|---|---|
| `board_id` | `ID!` |  |
| `config` | `String` |  |
| `event` | `WebhookEventType!` |  |
| `id` | `ID!` |  |

### `WebhookEventType` — ENUM

The webhook's target type.

| Enum value | Deprecated |
|---|---|
| `change_column_value` |  |
| `change_name` |  |
| `change_specific_column_value` |  |
| `change_status_column_value` |  |
| `change_subitem_column_value` |  |
| `change_subitem_name` |  |
| `create_column` |  |
| `create_item` |  |
| `create_subitem` |  |
| `create_subitem_update` |  |
| `create_update` |  |
| `delete_update` |  |
| `edit_update` |  |
| `item_archived` |  |
| `item_deleted` |  |
| `item_moved_to_any_group` |  |
| `item_moved_to_specific_group` |  |
| `item_restored` |  |
| `move_subitem` |  |
| `subitem_archived` |  |
| `subitem_deleted` |  |

### `WeekValue` — OBJECT

| Field | Type | Deprecated |
|---|---|---|
| `column` | `Column!` |  |
| `end_date` | `Date` |  |
| `id` | `ID!` |  |
| `start_date` | `Date` |  |
| `text` | `String` |  |
| `type` | `ColumnType!` |  |
| `value` | `JSON` |  |

### `Workspace` — OBJECT

A monday.com workspace.

| Field | Type | Deprecated |
|---|---|---|
| `account_product` | `AccountProduct` |  |
| `created_at` | `Date` |  |
| `description` | `String` |  |
| `id` | `ID` |  |
| `is_default_workspace` | `Boolean` |  |
| `kind` | `WorkspaceKind` |  |
| `name` | `String!` |  |
| `owners_subscribers` | `[User]` |  |
| `settings` | `WorkspaceSettings` |  |
| `state` | `State` |  |
| `team_owners_subscribers` | `[Team!]` |  |
| `teams_subscribers` | `[Team]` |  |
| `users_subscribers` | `[User]` |  |

### `WorkspaceIcon` — OBJECT

The workspace's icon.

| Field | Type | Deprecated |
|---|---|---|
| `color` | `String` |  |
| `image` | `String` |  |

### `WorkspaceKind` — ENUM

The workspace kinds available.

| Enum value | Deprecated |
|---|---|
| `closed` |  |
| `open` |  |
| `template` |  |

### `WorkspaceSettings` — OBJECT

The workspace's settings.

| Field | Type | Deprecated |
|---|---|---|
| `icon` | `WorkspaceIcon` |  |

### `WorkspaceSubscriberKind` — ENUM

The workspace subscriber kind.

| Enum value | Deprecated |
|---|---|
| `owner` |  |
| `subscriber` |  |

### `WorkspacesOrderBy` — ENUM

Options to order by.

| Enum value | Deprecated |
|---|---|
| `created_at` |  |

### `WorldClockValue` — OBJECT

| Field | Type | Deprecated |
|---|---|---|
| `column` | `Column!` |  |
| `id` | `ID!` |  |
| `text` | `String` |  |
| `timezone` | `String` |  |
| `type` | `ColumnType!` |  |
| `updated_at` | `Date` |  |
| `value` | `JSON` |  |

### `policy__Policy` — SCALAR
