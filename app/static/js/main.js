/**
 * Gmail Migrator - Main JavaScript
 */

console.log('main.js loaded');

// Make connectToGmail function globally available
window.connectToGmail = async function() {
    console.log('Global connectToGmail function called');
    console.trace('Stacktrace for connectToGmail call'); // Add stack trace to identify caller

    // First check if user is already authenticated
    const gmailToken = localStorage.getItem('gmailToken');
    if (gmailToken) {
        console.log('User already has a token, not starting OAuth flow');
        return; // Prevent OAuth flow if already signed in
    }

    try {
        logToConsole('Initiating direct Gmail OAuth flow...', 'info');

        // Skip the Google Sign-In popup and go directly to OAuth
        const authUrl = await getGmailOAuthUrl();
        console.log('Got auth URL:', authUrl);
        if (authUrl) {
            logToConsole('Redirecting to Gmail OAuth...', 'info');
            window.location.href = authUrl;
        } else {
            throw new Error('Failed to get OAuth URL');
        }
    } catch (error) {
        console.error('Error in connectToGmail:', error);
        logToConsole(`Error connecting to Gmail: ${error.message}`, 'error');
    }
};

// Add log entry to both console and UI
function logToConsole(message, type = 'info') {
    const timestamp = new Date().toLocaleTimeString();
    const logEntry = { timestamp, message, type };

    // Initialize migration.logs if it doesn't exist
    if (typeof migration === 'undefined' || !migration.logs) {
        window.migration = window.migration || {};
        migration.logs = migration.logs || [];
    }

    migration.logs.push(logEntry);

    // Log to browser console
    switch (type) {
        case 'error':
            console.error(`${timestamp} - ${message}`);
            break;
        case 'warning':
            console.warn(`${timestamp} - ${message}`);
            break;
        case 'success':
            console.log(`%c${timestamp} - ${message}`, 'color: green');
            break;
        default:
            console.log(`${timestamp} - ${message}`);
    }
}

// Function to handle Google Sign-In response
function handleGoogleSignIn(response) {
    logToConsole('Google Sign-In response received', 'info');

    if (response && response.credential) {
        logToConsole('Credential received, exchanging for access token', 'info');

        // Exchange the credential for an access token
        exchangeGoogleCredential(response.credential)
            .then(success => {
                if (success) {
                    logToConsole('Successfully connected to Gmail', 'success');
                    updateUIAfterGmailConnection(true);
                } else {
                    logToConsole('Failed to connect to Gmail', 'error');
                    updateUIAfterGmailConnection(false);
                }
            })
            .catch(error => {
                logToConsole('Error exchanging credential: ' + error, 'error');
                updateUIAfterGmailConnection(false);
            });
    } else {
        logToConsole('No credential in response', 'error');
        updateUIAfterGmailConnection(false);
    }
}

// Function to parse JWT token
function parseJwt(token) {
    try {
        // Get the payload part of the JWT
        const base64Url = token.split('.')[1];
        const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
        const jsonPayload = decodeURIComponent(atob(base64).split('').map(function(c) {
            return '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2);
        }).join(''));

        return JSON.parse(jsonPayload);
    } catch (error) {
        logToConsole('Error parsing JWT: ' + error.message, 'error');
        return null;
    }
}

// Function to exchange Google credential for Gmail access
async function exchangeGoogleCredential(credential) {
    logToConsole('Exchanging Google credential for Gmail access token', 'info');

    try {
        // Extract user info from the credential
        try {
            const payload = parseJwt(credential);
            localStorage.setItem('gmailUserInfo', JSON.stringify({
                name: payload.name,
                email: payload.email,
                picture: payload.picture
            }));
            logToConsole('User info stored: ' + payload.name + ' (' + payload.email + ')', 'info');
        } catch (error) {
            logToConsole('Error parsing JWT: ' + error, 'error');
        }

        // Exchange the credential with our backend
        const response = await fetch('/gmail/exchange-token', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ credential })
        });

        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`Server responded with ${response.status}: ${errorText}`);
        }

        const data = await response.json();

        if (data.access_token) {
            logToConsole('Received access token from server', 'success');
            localStorage.setItem('gmailToken', data.access_token);

            if (data.refresh_token) {
                localStorage.setItem('gmailRefreshToken', data.refresh_token);
                logToConsole('Refresh token stored', 'info');
            }

            return true;
        } else {
            logToConsole('No access token in response', 'error');
            return false;
        }
    } catch (error) {
        logToConsole('Error exchanging credential: ' + error, 'error');
        return false;
    }
}

// Function to update UI after Gmail connection attempt
function updateUIAfterGmailConnection(success) {
    if (success) {
        // Update the Gmail auth button
        updateGmailAuthButton();

        // Enable destination buttons
        const outlookAuthBtn = document.getElementById('outlookAuthBtn');
        const yahooAuthBtn = document.getElementById('yahooAuthBtn');

        if (outlookAuthBtn) outlookAuthBtn.disabled = false;
        if (yahooAuthBtn) yahooAuthBtn.disabled = false;

        // Show destination options
        showDestinationOptions();

        // Update state
        isGmailConnected = true;
    } else {
        // Show error message
        const gmailAuthContainer = document.getElementById('googleSignInButtonContainer');
        if (gmailAuthContainer) {
            const errorMessage = document.createElement('div');
            errorMessage.className = 'error-message';
            errorMessage.textContent = 'Failed to connect to Gmail. Please try again.';
            gmailAuthContainer.appendChild(errorMessage);

            // Remove the error message after 5 seconds
            setTimeout(() => {
                if (errorMessage.parentNode === gmailAuthContainer) {
                    gmailAuthContainer.removeChild(errorMessage);
                }
            }, 5000);
        }

        // Clear any stored tokens
        localStorage.removeItem('gmailToken');
        localStorage.removeItem('gmailRefreshToken');
        localStorage.removeItem('gmailUserInfo');

        // Update the Gmail auth button
        updateGmailAuthButton();
    }
}

// Function to update the Gmail auth button based on authentication state
function updateGmailAuthButton() {
    logToConsole('Updating Gmail auth button', 'info');
    const gmailAuthContainer = document.getElementById('googleSignInButtonContainer');

    if (!gmailAuthContainer) {
        logToConsole('Gmail auth container not found', 'error');
        return;
    }

    // Clear any existing content in the container
    gmailAuthContainer.innerHTML = '';

    // Check if we have a Gmail token
    const gmailToken = localStorage.getItem('gmailToken');
    const userInfoStr = localStorage.getItem('gmailUserInfo');

    if (gmailToken && userInfoStr) {
        try {
            const userInfo = JSON.parse(userInfoStr);
            logToConsole('User info found: ' + JSON.stringify(userInfo), 'info');

            // Create a custom button that matches Microsoft and Yahoo buttons
            const button = document.createElement('button');
            button.className = 'microsoft-auth-button'; // Reuse Microsoft button style for consistency
            button.style.display = 'flex';
            button.style.alignItems = 'center';
            button.style.justifyContent = 'center';
            button.style.width = '100%';
            button.style.padding = '10px 16px';
            button.style.backgroundColor = '#fff';
            button.style.color = '#5e5e5e';
            button.style.border = '1px solid #8c8c8c';
            button.style.borderRadius = '4px';
            button.style.fontSize = '14px';
            button.style.fontWeight = '500';
            button.style.cursor = 'pointer';
            button.style.marginBottom = '12px';
            button.style.height = '40px';

            // Create the button content
            button.innerHTML = `
                <img src="/static/img/google-logo.svg" alt="Google Logo" class="auth-button-icon" style="width: 20px; height: 20px; margin-right: 10px;">
                <span>${userInfo.email}</span>
                <svg width="18" height="18" viewBox="0 0 24 24" fill="#5f6368" style="position: absolute; right: 12px;">
                    <path d="M5 5h7V3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h7v-2H5V5zm16 7l-4-4v3H9v2h8v3l4-4z"></path>
                </svg>
            `;

            // Add click event to disconnect
            button.addEventListener('click', disconnectGmail);

            // Add the button to the container
            gmailAuthContainer.appendChild(button);

            // Enable the destination connection buttons
            const outlookAuthBtn = document.getElementById('outlookAuthBtn');
            const yahooAuthBtn = document.getElementById('yahooAuthBtn');

            if (outlookAuthBtn) outlookAuthBtn.disabled = false;
            if (yahooAuthBtn) yahooAuthBtn.disabled = false;

            // Update state
            isGmailConnected = true;

            // Show destination options
            showDestinationOptions();

        } catch (error) {
            logToConsole('Error parsing user info: ' + error, 'error');
            disconnectGmail();
        }
    } else {
        // Not connected, create a new Google Sign-In button that matches other buttons
        const button = document.createElement('button');
        button.className = 'microsoft-auth-button'; // Reuse Microsoft button style for consistency
        button.style.display = 'flex';
        button.style.alignItems = 'center';
        button.style.justifyContent = 'center';
        button.style.width = '100%';
        button.style.padding = '10px 16px';
        button.style.backgroundColor = '#fff';
        button.style.color = '#5e5e5e';
        button.style.border = '1px solid #8c8c8c';
        button.style.borderRadius = '4px';
        button.style.fontSize = '14px';
        button.style.fontWeight = '500';
        button.style.cursor = 'pointer';
        button.style.marginBottom = '12px';
        button.style.height = '40px';

        // Create the button content
        button.innerHTML = `
            <img src="/static/img/google-logo.svg" alt="Google Logo" class="auth-button-icon" style="width: 20px; height: 20px; margin-right: 10px;">
            <span>Sign in with Google</span>
        `;

        // Add click event to initiate Google sign-in
        button.addEventListener('click', async function() {
            const url = await getGmailOAuthUrl();
            if (url) {
                window.location.href = url;
            }
        });

        // Add the button to the container
        gmailAuthContainer.appendChild(button);
    }
}

// Function to disconnect from Gmail
function disconnectGmail() {
    logToConsole('Disconnecting from Gmail', 'info');

    // Clear tokens and user info
    localStorage.removeItem('gmailToken');
    localStorage.removeItem('gmailRefreshToken');
    localStorage.removeItem('gmailUserInfo');

    // Update the UI
    updateGmailAuthButton();

    // Disable destination buttons
    const outlookAuthBtn = document.getElementById('outlookAuthBtn');
    const yahooAuthBtn = document.getElementById('yahooAuthBtn');

    if (outlookAuthBtn) outlookAuthBtn.disabled = true;
    if (yahooAuthBtn) yahooAuthBtn.disabled = true;

    // Update state
    isGmailConnected = false;
}

// Function to get Gmail OAuth URL
async function getGmailOAuthUrl() {
    console.log('getGmailOAuthUrl function called');
    try {
        console.log('Fetching OAuth URL from server...');
        const response = await fetch('/gmail/auth-url', {
            method: 'GET',
            headers: {
                'Accept': 'application/json',
            }
        });

        console.log('OAuth URL response status:', response.status);

        if (!response.ok) {
            const errorText = await response.text();
            console.error('OAuth URL error response:', errorText);
            throw new Error(`HTTP error! Status: ${response.status}`);
        }

        const data = await response.json();
        console.log('OAuth URL response data:', data);
        return data.auth_url;
    } catch (error) {
        console.error('Error getting Gmail OAuth URL:', error);
        logToConsole(`Error getting Gmail OAuth URL: ${error.message}`, 'error');
        return null;
    }
}

// Function to show destination options
function showDestinationOptions() {
    console.log('showDestinationOptions called');
    // Toggle visibility of destination options container
    const destinationOptionsContainer = document.getElementById('destination-options-container');
    if (destinationOptionsContainer) {
        destinationOptionsContainer.classList.toggle('hidden');
        logToConsole('Showing destination options...', 'info');
    } else {
        console.error('Destination options container not found');
        logToConsole('Error: Could not find destination options container', 'error');
    }
}

// Function to initialize the application
function initializeApp() {
    logToConsole('Initializing application', 'info');

    // Disable destination buttons by default
    const outlookAuthBtn = document.getElementById('outlookAuthBtn');
    const yahooAuthBtn = document.getElementById('yahooAuthBtn');

    if (outlookAuthBtn) outlookAuthBtn.disabled = true;
    if (yahooAuthBtn) yahooAuthBtn.disabled = true;

    // Check if we have a Gmail token and enable destination buttons if we do
    const gmailToken = localStorage.getItem('gmailToken');
    if (gmailToken) {
        if (outlookAuthBtn) outlookAuthBtn.disabled = false;
        if (yahooAuthBtn) yahooAuthBtn.disabled = false;
    }

    // Initialize the Gmail auth button
    updateGmailAuthButton();

    // Initialize destination selection
    initializeDestinationSelection();

    // Initialize modals
    initializeModals();

    // Handle OAuth callback if present in URL
    handleOAuthCallback();

    // Initialize migration options
    initializeMigration();

    // Initialize advanced options toggle
    const advancedOptionsToggle = document.getElementById('advancedOptionsToggle');
    const advancedOptions = document.getElementById('advancedOptions');

    if (advancedOptionsToggle && advancedOptions) {
        advancedOptionsToggle.addEventListener('click', function() {
            advancedOptions.style.display = advancedOptions.style.display === 'block' ? 'none' : 'block';
            const chevron = advancedOptionsToggle.querySelector('.chevron');
            if (chevron) {
                chevron.style.transform = advancedOptions.style.display === 'block' ? 'rotate(180deg)' : 'rotate(0)';
            }
        });
    }

    // Initialize batch size slider
    const batchSizeSlider = document.getElementById('batchSizeSlider');
    const batchSizeValue = document.getElementById('batchSizeValue');
    const batchProcessingCheckbox = document.getElementById('batchProcessing');
    const batchSizeContainer = document.getElementById('batchSizeContainer');

    if (batchSizeSlider && batchSizeValue) {
        batchSizeSlider.addEventListener('input', function() {
            batchSizeValue.textContent = this.value + ' emails';
        });
    }

    if (batchProcessingCheckbox && batchSizeContainer) {
        batchProcessingCheckbox.addEventListener('change', function() {
            batchSizeContainer.style.display = this.checked ? 'block' : 'none';
        });
    }

    // Load OAuth settings from localStorage if available
    loadOAuthSettings();
}

// Document ready event
document.addEventListener('DOMContentLoaded', () => {
    console.log('DOMContentLoaded event fired');

    // Direct debug check of localStorage
    console.log('DIRECT CHECK - Gmail Token:', localStorage.getItem('gmailToken'));
    console.log('DIRECT CHECK - User Info:', localStorage.getItem('gmailUserInfo'));

    // Periodic checks of localStorage and UI state
    setInterval(() => {
        console.log('PERIODIC CHECK - Gmail Token:', localStorage.getItem('gmailToken'));
        console.log('PERIODIC CHECK - User Info:', localStorage.getItem('gmailUserInfo'));

        // Check if button is updated
        const directGmailAuthBtn = document.getElementById('directGmailAuthBtn');
        if (directGmailAuthBtn) {
            console.log('Button HTML:', directGmailAuthBtn.innerHTML.includes('user-info'));
        }
    }, 2000); // Check every 2 seconds

    // Get DOM elements
    connectGmailBtn = document.getElementById('connectGmail');
    connectDestinationBtn = document.getElementById('connectDestination');
    migrationForm = document.getElementById('migrationForm');
    startMigrationBtn = document.getElementById('startMigration');
    progressContainer = document.getElementById('progressContainer');
    progressBar = document.getElementById('progressBar');
    progressText = document.getElementById('progressText');
    logContainer = document.getElementById('logContainer');

    // Log element presence
    console.log('connectGmailBtn found:', !!connectGmailBtn);

    // Setup click handlers
    if (connectGmailBtn) {
        connectGmailBtn.addEventListener('click', function(event) {
            // Prevent default action to ensure we control the flow
            event.preventDefault();

            // Check authentication first
            const gmailToken = localStorage.getItem('gmailToken');
            if (gmailToken) {
                console.log('User is authenticated, showing disconnect prompt');
                if (confirm('Do you want to disconnect from Gmail?')) {
                    disconnectGmail();
                } else {
                    console.log('User cancelled disconnect action');
                }
            } else {
                console.log('User is not authenticated, initiating OAuth flow');
                connectToGmail();
            }
        });
        console.log('Added smart click listener to connectGmailBtn');
    }

    // Add direct Gmail auth button click handler with debouncing
    const directGmailAuthBtn = document.getElementById('directGmailAuthBtn');
    console.log('directGmailAuthBtn found:', !!directGmailAuthBtn);

    if (directGmailAuthBtn) {
        // Remove any existing click listeners to prevent duplicates
        directGmailAuthBtn.replaceWith(directGmailAuthBtn.cloneNode(true));

        // Get the fresh copy after replacement
        const freshAuthBtn = document.getElementById('directGmailAuthBtn');

        // Set a single click listener
        freshAuthBtn.addEventListener('click', function handleAuthButtonClick(event) {
            // Prevent default action
            event.preventDefault();

            console.log('Gmail Auth button clicked');

            // Detailed check for authentication
            const gmailToken = localStorage.getItem('gmailToken');
            console.log('Token check on click:', gmailToken ? 'FOUND' : 'NOT FOUND');

            if (gmailToken) {
                console.log('USER IS AUTHENTICATED - showing disconnect prompt');
                if (confirm('Do you want to disconnect from Gmail?')) {
                    console.log('User confirmed disconnect, proceeding with disconnection');
                    disconnectGmail();
                } else {
                    console.log('User CANCELLED disconnect action - doing nothing');
                }
            } else {
                console.log('USER IS NOT AUTHENTICATED - proceeding with OAuth flow');
                connectToGmail();
            }
        });

        console.log('Added exclusive click handler to Gmail Auth button');
    } else {
        console.error('directGmailAuthBtn not found in DOM');
    }

    if (connectDestinationBtn) {
        connectDestinationBtn.addEventListener('click', showDestinationOptions);
    }

    if (startMigrationBtn) {
        startMigrationBtn.addEventListener('click', startMigration);
    }

    // Initialize modals if present
    const modals = document.querySelectorAll('.modal');
    if (modals.length > 0) {
        initializeModals();
    }

    // Initialize application state
    initializeApp();

    // Check for OAuth callback parameters
    handleOAuthCallback();

    // Force UI update for testing
    console.log('Forcing UI update based on authentication');
    updateUIBasedOnAuthentication();

    // OAuth Settings Modal
    const oauthSettingsBtn = document.getElementById('oauthSettingsBtn');
    const oauthSettingsModal = document.getElementById('oauthSettingsModal');
    const closeModalBtn = document.querySelector('.close-modal');
    const tabButtons = document.querySelectorAll('.tab-button');
    const tabContents = document.querySelectorAll('.tab-content');
    const oauthForms = {
        gmail: document.getElementById('gmailOAuthForm'),
        outlook: document.getElementById('outlookOAuthForm'),
        yahoo: document.getElementById('yahooOAuthForm')
    };

    // Open OAuth settings modal
    oauthSettingsBtn.addEventListener('click', () => {
        oauthSettingsModal.style.display = 'block';
        // Load saved OAuth settings
        loadOAuthSettings();
    });

    // Close OAuth settings modal
    closeModalBtn.addEventListener('click', () => {
        oauthSettingsModal.style.display = 'none';
    });

    // Close modal if clicked outside
    window.addEventListener('click', (event) => {
        if (event.target === oauthSettingsModal) {
            oauthSettingsModal.style.display = 'none';
        }
    });

    // Tab switching
    tabButtons.forEach(button => {
        button.addEventListener('click', () => {
            // Remove active class from all buttons and contents
            tabButtons.forEach(btn => btn.classList.remove('active'));
            tabContents.forEach(content => content.classList.remove('active'));

            // Add active class to current button and content
            button.classList.add('active');
            const tabName = button.getAttribute('data-tab');
            document.getElementById(`${tabName}-tab`).classList.add('active');
        });
    });

    // Save OAuth settings
    Object.keys(oauthForms).forEach(provider => {
        oauthForms[provider].addEventListener('submit', (e) => {
            e.preventDefault();

            const formData = new FormData(oauthForms[provider]);
            const settings = {
                clientId: formData.get('clientId'),
                clientSecret: formData.get('clientSecret'),
                redirectUri: formData.get('redirectUri')
            };

            // Save to localStorage (encrypted in a real app)
            localStorage.setItem(`${provider}OAuthConfig`, JSON.stringify(settings));

            logToConsole(`${provider.charAt(0).toUpperCase() + provider.slice(1)} OAuth settings saved`, 'success');
        });
    });

    // Load OAuth settings from storage
    function loadOAuthSettings() {
        Object.keys(oauthForms).forEach(provider => {
            const savedSettings = localStorage.getItem(`${provider}OAuthConfig`);
            if (savedSettings) {
                const settings = JSON.parse(savedSettings);

                // Fill in the form
                document.getElementById(`${provider}ClientId`).value = settings.clientId || '';
                document.getElementById(`${provider}ClientSecret`).value = settings.clientSecret || '';
                document.getElementById(`${provider}RedirectUri`).value = settings.redirectUri || '';
            }
        });
    }

    // Function to update the destination connection UI
    function updateDestinationConnectionUI(connected) {
        const connectDestinationBtn = document.getElementById('connectDestination');

        if (connected) {
            isDestinationConnected = true;

            if (connectDestinationBtn) {
                connectDestinationBtn.textContent = 'Destination Connected';
                connectDestinationBtn.classList.add('connected');
                connectDestinationBtn.disabled = true;
            }

            // Enable start migration button if both source and destination are connected
            if (isGmailConnected && startMigrationBtn) {
            startMigrationBtn.disabled = false;
            }
        }
    }

    // Function to initialize migration
    function initializeMigration() {
        // Reset migration state
        migration.isRunning = false;
        migration.processed = 0;
        migration.total = 0;
        migration.logs = [];

        // Clear UI elements
        const migrationLog = document.getElementById('migrationLog');
        if (migrationLog) {
            migrationLog.innerHTML = '';
        }
    }

    // Advanced Options Toggle
    const advancedOptionsToggle = document.getElementById('advancedOptionsToggle');
    const advancedOptions = document.getElementById('advancedOptions');
    if (advancedOptionsToggle && advancedOptions) {
        const chevron = advancedOptionsToggle.querySelector('.chevron');

        advancedOptionsToggle.addEventListener('click', function() {
            advancedOptions.classList.toggle('open');
            chevron.classList.toggle('open');
        });
    }

    // Handle destination provider selection
    initializeDestinationSelection();

    // Make connectToOutlook and connectToYahoo available globally
    window.connectToOutlook = connectToOutlook;
    window.connectToYahoo = connectToYahoo;
});

// Function to initialize modal dialogs
function initializeModals() {
    console.log('Initializing modals');
    const modals = document.querySelectorAll('.modal');
    const closeBtns = document.querySelectorAll('.close-modal');

    // Set up close buttons
    closeBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const modal = btn.closest('.modal');
            if (modal) {
                modal.style.display = 'none';
            }
        });
    });

    // Close modal when clicking outside
    window.addEventListener('click', (event) => {
        modals.forEach(modal => {
            if (event.target === modal) {
                modal.style.display = 'none';
            }
        });
    });

    console.log('Modal initialization complete');
}

// Check for existing tokens and update UI accordingly
function updateUIBasedOnAuthentication() {
    console.log('Running updateUIBasedOnAuthentication');

    // Check if user is already authenticated with Gmail
    const gmailToken = localStorage.getItem('gmailToken');
    console.log('Gmail token exists:', !!gmailToken);

    if (gmailToken) {
        console.log('Found Gmail token, updating UI elements');
        logToConsole('Found existing Gmail token, updating UI', 'info');
        isGmailConnected = true;

        // Update Gmail connection button if it exists
        const connectGmailBtn = document.getElementById('connectGmail');
        console.log('connectGmailBtn exists:', !!connectGmailBtn);

        if (connectGmailBtn) {
            connectGmailBtn.textContent = 'Connected to Gmail';
            connectGmailBtn.classList.remove('primary');
            connectGmailBtn.classList.add('secondary');
            connectGmailBtn.classList.add('connected');
        }

        // Check for direct Gmail auth button
        const directGmailAuthBtn = document.getElementById('directGmailAuthBtn');
        console.log('directGmailAuthBtn exists:', !!directGmailAuthBtn);

        // Update the direct Gmail auth button
        if (directGmailAuthBtn) {
            console.log('Calling updateGmailAuthButton to update button appearance');
            updateGmailAuthButton();
        } else {
            console.error('directGmailAuthBtn not found while trying to update UI');
        }

        // Enable the destination connection button
        const connectDestinationBtn = document.getElementById('connectDestination');
        if (connectDestinationBtn) {
            connectDestinationBtn.disabled = false;
        }

        logToConsole('UI updated to reflect Gmail authentication', 'success');
    } else {
        console.log('No Gmail token found, user is not authenticated');
    }

    // Check for destination authentication (similar logic)
    // This would be implemented based on your destination providers
}

// Function to handle OAuth callback parameters from URL
function handleOAuthCallback() {
    console.log('Checking for OAuth callback parameters');

    // Get URL parameters
    const urlParams = new URLSearchParams(window.location.search);
    const code = urlParams.get('code');
    const state = urlParams.get('state');

    // If we have code or state, we might be in a callback
    if (code || state) {
        console.log('Found OAuth parameters in URL');
        logToConsole('Processing OAuth callback...', 'info');

        // Handle processing if needed - usually this is handled by the backend

        // Clean up URL - remove parameters to prevent reprocessing on refresh
        if (history.pushState) {
            const newurl = window.location.protocol + '//' + window.location.host + window.location.pathname;
            window.history.pushState({path: newurl}, '', newurl);
            console.log('Cleaned up URL parameters');
        }
    } else {
        console.log('No OAuth callback parameters found in URL');
    }
}

// Function to handle destination provider selection
function initializeDestinationSelection() {
    console.log('Initializing destination selection');
    const outlookAuthBtn = document.getElementById('outlookAuthBtn');
    const yahooAuthBtn = document.getElementById('yahooAuthBtn');
    const outlookAuthSection = document.getElementById('outlookAuthSection');
    const yahooAuthSection = document.getElementById('yahooAuthSection');

    console.log('Outlook auth button found:', !!outlookAuthBtn);
    console.log('Yahoo auth button found:', !!yahooAuthBtn);
    console.log('Outlook auth section found:', !!outlookAuthSection);
    console.log('Yahoo auth section found:', !!yahooAuthSection);

    if (!outlookAuthBtn || !yahooAuthBtn) {
        console.error('Destination auth buttons not found');
        return;
    }

    // Add click event listeners to auth buttons
    outlookAuthBtn.addEventListener('click', function(e) {
        // Prevent default to handle the auth flow ourselves
        e.preventDefault();

        const provider = this.getAttribute('data-provider');
        console.log('Outlook auth button clicked, provider:', provider);

        // Store selected provider
        localStorage.setItem('selectedDestinationProvider', 'outlook');
        console.log('Provider saved to localStorage: outlook');

        // Call the connect function directly
        connectToOutlook();
    });

    yahooAuthBtn.addEventListener('click', function(e) {
        // Prevent default to handle the auth flow ourselves
        e.preventDefault();

        const provider = this.getAttribute('data-provider');
        console.log('Yahoo auth button clicked, provider:', provider);

        // Store selected provider
        localStorage.setItem('selectedDestinationProvider', 'yahoo');
        console.log('Provider saved to localStorage: yahoo');

        // Call the connect function directly
        connectToYahoo();
    });

    // Initialize the global connect functions
    window.connectToOutlook = function() {
        console.log('Global connectToOutlook function called');
        // This would be implemented with actual OAuth flow
        // For now, we'll simulate a successful connection

        setTimeout(() => {
            // Update button to show connected state
            outlookAuthBtn.classList.add('connected');
            outlookAuthBtn.innerHTML = `
                <img src="/static/img/microsoft-logo.svg" alt="Microsoft Logo" class="auth-button-icon">
                <span>Connected to Microsoft</span>
            `;

            // Enable start migration button
            const startMigrationBtn = document.getElementById('startMigration');
            if (startMigrationBtn) {
                startMigrationBtn.disabled = false;
            }
        }, 1500);
    };

    window.connectToYahoo = function() {
        console.log('Global connectToYahoo function called');
        // This would be implemented with actual OAuth flow
        // For now, we'll simulate a successful connection

        setTimeout(() => {
            // Update button to show connected state
            yahooAuthBtn.classList.add('connected');
            yahooAuthBtn.innerHTML = `
                <img src="/static/img/yahoo-white-icon.svg" alt="Yahoo Logo" class="auth-button-icon">
                <span>Connected to Yahoo</span>
            `;

            // Enable start migration button
            const startMigrationBtn = document.getElementById('startMigration');
            if (startMigrationBtn) {
                startMigrationBtn.disabled = false;
            }
        }, 1500);
    };
}
