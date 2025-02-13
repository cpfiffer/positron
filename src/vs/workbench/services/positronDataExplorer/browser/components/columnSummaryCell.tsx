/*---------------------------------------------------------------------------------------------
 *  Copyright (C) 2024 Posit Software, PBC. All rights reserved.
 *  Licensed under the Elastic License 2.0. See LICENSE.txt for license information.
 *--------------------------------------------------------------------------------------------*/

// CSS.
import 'vs/css!./columnSummaryCell';

// React.
import * as React from 'react';
import { useRef, useState } from 'react'; // eslint-disable-line no-duplicate-imports

// Other dependencies.
import { IHoverService } from 'vs/platform/hover/browser/hover';
import { HoverPosition } from 'vs/base/browser/ui/hover/hoverWidget';
import { positronClassNames } from 'vs/base/common/positronUtilities';
import { ProfileDate } from 'vs/workbench/services/positronDataExplorer/browser/components/profileDate';
import { ProfileNumber } from 'vs/workbench/services/positronDataExplorer/browser/components/profileNumber';
import { ProfileString } from 'vs/workbench/services/positronDataExplorer/browser/components/profileString';
import { ProfileBoolean } from 'vs/workbench/services/positronDataExplorer/browser/components/profileBoolean';
import { ProfileDatetime } from 'vs/workbench/services/positronDataExplorer/browser/components/profileDatetime';
import { ColumnNullPercent } from 'vs/workbench/services/positronDataExplorer/browser/components/columnNullPercent';
import { TableSummaryDataGridInstance } from 'vs/workbench/services/positronDataExplorer/browser/tableSummaryDataGridInstance';
import { ColumnDisplayType, ColumnProfileType, ColumnSchema } from 'vs/workbench/services/languageRuntime/common/positronDataExplorerComm';
import { dataExplorerExperimentalFeatureEnabled } from 'vs/workbench/services/positronDataExplorer/common/positronDataExplorerExperimentalConfig';

/**
 * ColumnSummaryCellProps interface.
 */
interface ColumnSummaryCellProps {
	hoverService: IHoverService;
	instance: TableSummaryDataGridInstance;
	columnSchema: ColumnSchema;
	columnIndex: number;
	onDoubleClick: () => void;
}

/**
 * ColumnSummaryCell component.
 * @param props A ColumnSummaryCellProps that contains the component properties.
 * @returns The rendered component.
 */
export const ColumnSummaryCell = (props: ColumnSummaryCellProps) => {
	// Reference hooks.
	const dataTypeRef = useRef<HTMLDivElement>(undefined!);

	// State hooks.
	const [mouseInside, setMouseInside] = useState(false);

	// Set the data type icon.
	const dataTypeIcon = (() => {
		// Determine the alignment based on type.
		switch (props.columnSchema.type_display) {
			case ColumnDisplayType.Number:
				return 'codicon-positron-data-type-number';

			case ColumnDisplayType.Boolean:
				return 'codicon-positron-data-type-boolean';

			case ColumnDisplayType.String:
				return 'codicon-positron-data-type-string';

			case ColumnDisplayType.Date:
				return 'codicon-positron-data-type-date';

			case ColumnDisplayType.Datetime:
				return 'codicon-positron-data-type-date-time';

			case ColumnDisplayType.Time:
				return 'codicon-positron-data-type-time';

			case ColumnDisplayType.Object:
				return 'codicon-positron-data-type-object';

			case ColumnDisplayType.Array:
				return 'codicon-positron-data-type-array';

			case ColumnDisplayType.Struct:
				return 'codicon-positron-data-type-struct';

			case ColumnDisplayType.Unknown:
				return 'codicon-positron-data-type-unknown';

			// This shouldn't ever happen.
			default:
				return 'codicon-question';
		}
	})();

	// Set the profile component for the column.
	const profile = (() => {

		// Determine the alignment based on type.
		switch (props.columnSchema.type_display) {
			case ColumnDisplayType.Number:
				return <ProfileNumber
					instance={props.instance}
					columnIndex={props.columnIndex}
				/>;

			case ColumnDisplayType.Boolean:
				return <ProfileBoolean
					instance={props.instance}
					columnIndex={props.columnIndex}
				/>;

			case ColumnDisplayType.String:
				return <ProfileString
					instance={props.instance}
					columnIndex={props.columnIndex}
				/>;

			case ColumnDisplayType.Date:
				return <ProfileDate
					instance={props.instance}
					columnIndex={props.columnIndex}
				/>;

			case ColumnDisplayType.Datetime:
				return <ProfileDatetime
					instance={props.instance}
					columnIndex={props.columnIndex}
				/>;

			case ColumnDisplayType.Time:
				return null;

			case ColumnDisplayType.Array:
				return null;

			case ColumnDisplayType.Struct:
				return null;

			case ColumnDisplayType.Unknown:
				return null;

			// This shouldn't ever happen.
			default:
				return null;
		}
	})();

	// Get the expanded state of the column.
	const expanded = props.instance.isColumnExpanded(props.columnIndex);

	// Get the column null percent.
	const columnNullPercent = props.instance.getColumnNullPercent(props.columnIndex);

	// Check if the summary stats panel is supported.
	const profileFeatures = props.instance.getSupportedFeatures().get_column_profiles;
	const summaryStatsStatus = profileFeatures.supported_types.filter((status) => {
		return status.profile_type === ColumnProfileType.SummaryStats;
	});
	let summarySupported = false;
	if (summaryStatsStatus.length === 1) {
		summarySupported = dataExplorerExperimentalFeatureEnabled(summaryStatsStatus[0].support_status, props.instance.configurationService);
	}

	if (props.columnSchema.type_display === ColumnDisplayType.Object ||
		props.columnSchema.type_display === ColumnDisplayType.Unknown) {
		summarySupported = false;
	}

	// Render.
	return (
		<div
			className='column-summary'
			onDoubleClick={props.onDoubleClick}
			onMouseEnter={() => setMouseInside(true)}
			onMouseLeave={() => setMouseInside(false)}
			onMouseDown={() => {
				props.instance.scrollToRow(props.columnIndex);
				props.instance.setCursorRow(props.columnIndex);
			}}
		>
			{(mouseInside || props.columnIndex === props.instance.cursorRowIndex) &&
				<div className='cursor-background' />
			}
			<div className='basic-info'>
				<div
					className={positronClassNames('expand-collapse-button',
						{ 'disabled': !summarySupported })}
					onClick={summarySupported ? () =>
						props.instance.toggleExpandColumn(props.columnIndex) : undefined
					}
				>
					{expanded ?
						<div className={`expand-collapse-icon codicon codicon-chevron-down`} /> :
						<div className={`expand-collapse-icon codicon codicon-chevron-right`} />
					}
				</div>

				<div
					ref={dataTypeRef}
					className={`data-type-icon codicon ${dataTypeIcon}`}
					onMouseOver={() =>
						props.hoverService.showHover({
							content: `${props.columnSchema.type_name}`,
							target: dataTypeRef.current,
							position: {
								hoverPosition: HoverPosition.ABOVE,
							},
							persistence: {
								hideOnHover: false
							},
							appearance: {
								showHoverHint: true,
								showPointer: true
							}
						}, false)
					}
					onMouseLeave={() => props.hoverService.hideHover()}
				/>
				<div className='column-name'>
					{props.columnSchema.column_name}
				</div>

				{columnNullPercent !== undefined &&
					<ColumnNullPercent columnNullPercent={columnNullPercent} />
				}
			</div>
			{expanded &&
				<div className='profile-info'>
					{profile}
				</div>
			}
		</div>
	);
};
