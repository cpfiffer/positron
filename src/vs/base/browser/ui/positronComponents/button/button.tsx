/*---------------------------------------------------------------------------------------------
 *  Copyright (C) 2024 Posit Software, PBC. All rights reserved.
 *  Licensed under the Elastic License 2.0. See LICENSE.txt for license information.
 *--------------------------------------------------------------------------------------------*/

// CSS.
import 'vs/css!./button';


// React.
import * as React from 'react';
import { forwardRef, KeyboardEvent, MouseEvent, PropsWithChildren, useImperativeHandle, useRef } from 'react'; // eslint-disable-line no-duplicate-imports

// Other dependencies.
import { positronClassNames } from 'vs/base/common/positronUtilities';
import { IHoverManager } from 'vs/platform/positronActionBar/browser/positronActionBarState';

/**
 * MouseTrigger enumeration.
 */
export enum MouseTrigger {
	Click,
	MouseDown
}

/**
 * KeyboardModifiers interface.
 */
export interface KeyboardModifiers {
	altKey: boolean;
	ctrlKey: boolean;
	metaKey: boolean;
	shiftKey: boolean;
}

/**
 * ButtonProps interface.
 */
interface ButtonProps {
	readonly hoverManager?: IHoverManager;
	readonly className?: string;
	readonly disabled?: boolean;
	readonly ariaLabel?: string;
	readonly tooltip?: string | (() => string | undefined);
	readonly mouseTrigger?: MouseTrigger;
	readonly onBlur?: () => void;
	readonly onFocus?: () => void;
	readonly onPressed?: (e: KeyboardModifiers) => void;
}

/**
 * Button component.
 * @param props A PropsWithChildren<ButtonProps> that contains the component properties.
 * @returns The rendered component.
 */
export const Button = forwardRef<HTMLButtonElement, PropsWithChildren<ButtonProps>>((props, ref) => {
	// Reference hooks.
	const buttonRef = useRef<HTMLButtonElement>(undefined!);
	useImperativeHandle(ref, () => buttonRef.current, []);

	/**
	 * onKeyDown event handler.
	 * @param e A KeyboardEvent<HTMLDivElement> that describes a user interaction with the keyboard.
	 */
	const keyDownHandler = (e: KeyboardEvent<HTMLButtonElement>) => {
		// Process the key down event.
		switch (e.code) {
			// Space or Enter trigger the onPressed event.
			case 'Space':
			case 'Enter':
				// Consume the event.
				e.preventDefault();
				e.stopPropagation();

				// Raise the onPressed event if the button isn't disabled.
				if (!props.disabled && props.onPressed) {
					props.onPressed(e);
				}
				break;
		}
	};

	/**
	 * onClick event handler.
	 * @param e A MouseEvent<HTMLDivElement> that describes a user interaction with the mouse.
	 */
	const clickHandler = (e: MouseEvent<HTMLButtonElement>) => {
		// If the mouse trigger is click, handle the event.
		if (props.mouseTrigger === undefined || props.mouseTrigger === MouseTrigger.Click) {
			// Consume the event.
			e.preventDefault();
			e.stopPropagation();

			// Raise the onPressed event if the button isn't disabled.
			if (!props.disabled && props.onPressed) {
				props.onPressed(e);
			}
		}
	};

	/**
	 * onMouseEnter event handler.
	 * @param e A MouseEvent<HTMLDivElement> that describes a user interaction with the mouse.
	 */
	const mouseEnterHandler = (e: MouseEvent<HTMLButtonElement>) => {
		// If there's a hover manager, see if there's a tooltip.
		if (props.hoverManager) {
			// Get the tooltip.
			const tooltip = (() => {
				if (!props.tooltip) {
					// There isn't a tooltip.
					return undefined;
				} else if (typeof props.tooltip === 'string') {
					// Return the string tooltip.
					return props.tooltip;
				} else {
					// Return the dynamic tooltip.
					return props.tooltip();
				}
			})();

			// If there's a tooltip, show it.
			if (tooltip) {
				props.hoverManager.showHover({
					content: tooltip,
					target: buttonRef.current,
					persistence: {
						hideOnKeyDown: true,
						hideOnHover: false
					},
					appearance: {
						showPointer: true
					}
				}, false);
			}
		}
	};

	/**
	 * onMouseLeave event handler.
	 * @param e A MouseEvent<HTMLDivElement> that describes a user interaction with the mouse.
	 */
	const mouseLeaveHandler = (e: MouseEvent<HTMLButtonElement>) => {
		// If there's a hover manager, hide hover.
		if (props.hoverManager) {
			props.hoverManager.hideHover();
		}
	};

	/**
	 * onMouseDown event handler.
	 * @param e A MouseEvent<HTMLDivElement> that describes a user interaction with the mouse.
	 */
	const mouseDownHandler = (e: MouseEvent<HTMLButtonElement>) => {
		// If the mouse trigger is mouse down, handle the event.
		if (props.mouseTrigger === MouseTrigger.MouseDown) {
			// Consume the event.
			e.preventDefault();
			e.stopPropagation();

			// Raise the onPressed event if the button isn't disabled.
			if (!props.disabled && props.onPressed) {
				props.onPressed(e);
			}
		}
	};

	// Render.
	return (
		<button
			ref={buttonRef}
			className={positronClassNames(
				'positron-button',
				props.className,
				{ 'disabled': props.disabled }
			)}
			tabIndex={0}
			disabled={props.disabled}
			role='button'
			aria-label={props.ariaLabel}
			aria-disabled={props.disabled ? 'true' : undefined}
			onFocus={props.onFocus}
			onBlur={props.onBlur}
			onKeyDown={keyDownHandler}
			onClick={clickHandler}
			onMouseEnter={mouseEnterHandler}
			onMouseLeave={mouseLeaveHandler}
			onMouseDown={mouseDownHandler}
		>
			{props.children}
		</button>
	);
});

// Set the display name.
Button.displayName = 'Button';
