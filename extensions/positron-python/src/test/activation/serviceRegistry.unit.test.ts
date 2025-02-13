// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT License.
import { instance, mock, verify } from 'ts-mockito';

import { ExtensionActivationManager } from '../../client/activation/activationManager';
import { ExtensionSurveyPrompt } from '../../client/activation/extensionSurvey';
import { LanguageServerOutputChannel } from '../../client/activation/common/outputChannel';
import { registerTypes } from '../../client/activation/serviceRegistry';
import {
    IExtensionActivationManager,
    IExtensionSingleActivationService,
    ILanguageServerOutputChannel,
} from '../../client/activation/types';
import { ServiceManager } from '../../client/ioc/serviceManager';
import { IServiceManager } from '../../client/ioc/types';
import { LoadLanguageServerExtension } from '../../client/activation/common/loadLanguageServerExtension';

suite('Unit Tests - Language Server Activation Service Registry', () => {
    let serviceManager: IServiceManager;

    setup(() => {
        serviceManager = mock(ServiceManager);
    });

    test('Ensure common services are registered', async () => {
        registerTypes(instance(serviceManager));

        verify(
            serviceManager.add<IExtensionActivationManager>(IExtensionActivationManager, ExtensionActivationManager),
        ).once();
        verify(
            serviceManager.addSingleton<ILanguageServerOutputChannel>(
                ILanguageServerOutputChannel,
                LanguageServerOutputChannel,
            ),
        ).once();
        // --- Start Positron ---
        // Extension survey prompt was removed in https://github.com/posit-dev/positron-python/pull/153.
        verify(
            serviceManager.addSingleton<IExtensionSingleActivationService>(
                IExtensionSingleActivationService,
                ExtensionSurveyPrompt,
            ),
        ).never();
        // --- End Positron ---
        verify(
            serviceManager.addSingleton<IExtensionSingleActivationService>(
                IExtensionSingleActivationService,
                LoadLanguageServerExtension,
            ),
        ).once();
    });
});
