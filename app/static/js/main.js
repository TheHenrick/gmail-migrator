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

// Google Sign-In callback function (must be in global scope)
function handleGoogleSignIn(response) {
    logToConsole('Google Sign-In response received', 'info');

    // The response contains a credential with the ID token
    if (response && response.credential) {
        const credential = response.credential;
        logToConsole('Credential received, exchanging for Gmail access', 'info');

        // Parse the JWT to get user info
        const userInfo = parseJwt(credential);

        // Store user info in localStorage for later use
        if (userInfo) {
            localStorage.setItem('gmailUserInfo', JSON.stringify({
                name: userInfo.name,
                email: userInfo.email,
                picture: userInfo.picture
            }));
        }

        // Exchange the Google credential for Gmail OAuth access
        exchangeGoogleCredential(credential);
    } else {
        logToConsole('Invalid Google Sign-In response', 'error');
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

// Function to exchange Google credential for Gmail OAuth access
async function exchangeGoogleCredential(credential) {
    try {
        logToConsole('Sending credential to server for exchange', 'info');

        const response = await fetch('/gmail/google-signin', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ credential }),
        });

        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
        }

        const data = await response.json();

        // Check if OAuth consent is required
        if (data.requires_oauth_consent) {
            logToConsole(`Redirecting to Google OAuth consent for ${data.email}`, 'info');
            // Redirect to the authorization URL
            window.location.href = data.auth_url;
            return;
        }

        // If we have an access token, store it and update UI
        if (data.access_token) {
            localStorage.setItem('gmailAccessToken', data.access_token);
            updateUIAfterGmailConnection(true);

            // Log success
            logToConsole('Successfully connected to Gmail', 'success');
        } else {
            throw new Error('No access token received');
        }
    } catch (error) {
        logToConsole(`Error connecting to Gmail: ${error.message}`, 'error');
        updateUIAfterGmailConnection(false);
    }
}

// Function to update UI after Gmail connection attempt
function updateUIAfterGmailConnection(success) {
    const connectDestinationBtn = document.getElementById('connectDestination');
    const googleSignInBtn = document.querySelector('.g_id_signin');
    const directGmailAuthBtn = document.getElementById('directGmailAuthBtn');

    if (success) {
        // Update state
        isGmailConnected = true;

        // Update UI - hide the Google Sign-In button and show user profile
        if (googleSignInBtn) {
            const container = document.getElementById('googleSignInButtonContainer');
            googleSignInBtn.style.display = 'none';
        }

        // Update the direct Gmail auth button if it exists
        if (directGmailAuthBtn) {
            updateGmailAuthButton();
        }

        // Get user info from localStorage
        const userInfoString = localStorage.getItem('gmailUserInfo');

        if (userInfoString) {
            try {
                const userInfo = JSON.parse(userInfoString);

                // Create user profile element
                const userProfile = document.createElement('div');
                userProfile.className = 'user-profile';

                // Build profile HTML with user info
                userProfile.innerHTML = `
                    <img src="${userInfo.picture}" alt="Profile" class="user-profile-image">
                    <div class="user-profile-info">
                        <div class="user-profile-name">${userInfo.name}</div>
                        <div class="user-profile-email">${userInfo.email}</div>
                    </div>
                    <div class="connection-status">
                        <span class="checkmark">✓</span> Connected
                    </div>
                `;

                container.appendChild(userProfile);
        } catch (error) {
                // If there's an error parsing user info, fall back to basic success indicator
                const successIndicator = document.createElement('div');
                successIndicator.className = 'success-indicator';
                successIndicator.innerHTML = '<span class="checkmark">✓</span> Connected to Gmail';
                container.appendChild(successIndicator);
            }
        } else {
            // No user info available, show basic success indicator
            const successIndicator = document.createElement('div');
            successIndicator.className = 'success-indicator';
            successIndicator.innerHTML = '<span class="checkmark">✓</span> Connected to Gmail';
            container.appendChild(successIndicator);
        }

        // Enable destination selection
        if (connectDestinationBtn) {
            connectDestinationBtn.disabled = false;
        }
    } else {
        // Update state
        isGmailConnected = false;

        // Update UI to show an error state
        if (googleSignInBtn) {
            const container = document.getElementById('googleSignInButtonContainer');
            const errorMessage = document.createElement('div');
            errorMessage.className = 'error-message';
            errorMessage.textContent = 'Connection failed. Please try again.';
            container.appendChild(errorMessage);
        }
    }
}

// Function to update the Gmail Auth button to show user info
function updateGmailAuthButton() {
    console.log('updateGmailAuthButton called');
    const directGmailAuthBtn = document.getElementById('directGmailAuthBtn');
    if (!directGmailAuthBtn) {
        console.error('directGmailAuthBtn not found in DOM');
        return;
    }

    console.log('Found directGmailAuthBtn element:', directGmailAuthBtn);

    // Get user info from localStorage
    const userInfoString = localStorage.getItem('gmailUserInfo');
    const gmailToken = localStorage.getItem('gmailToken');

    console.log('gmailToken exists:', !!gmailToken);
    console.log('userInfoString exists:', !!userInfoString);

    if (gmailToken) {
        try {
            // If we have user info, parse it and use it
            let userInfo = { name: 'Gmail User', email: 'gmail@user.com', picture: '' };
            if (userInfoString) {
                try {
                    userInfo = JSON.parse(userInfoString);
                    console.log('Parsed user info:', JSON.stringify(userInfo, null, 2));
                    console.log('Profile picture URL:', userInfo.picture);
                } catch (e) {
                    console.error('Error parsing user info:', e);
                }
            } else {
                console.log('No user info found, using default values');
            }

            // Using Apple HIG styled button with Google aesthetics
            console.log('Updating button HTML with user info');

            // Determine avatar content - use picture if available, otherwise first letter of name
            let avatarContent = '';
            if (userInfo.picture && userInfo.picture.trim() !== '') {
                console.log('Using profile picture for avatar');
                avatarContent = `<img src="${userInfo.picture}" alt="Profile" />`;
            } else {
                console.log('Using first letter as avatar:', userInfo.name ? userInfo.name.charAt(0).toUpperCase() : 'G');
                avatarContent = userInfo.name ? userInfo.name.charAt(0).toUpperCase() : 'G';
            }

            // Log the final HTML we're going to use
            const newButtonHTML = `
                <div class="auth-button-content">
                    <span class="user-avatar">${avatarContent}</span>
                    <span class="auth-button-text">${userInfo.email || 'Gmail User'}</span>
                </div>
            `;
            console.log('New button HTML:', newButtonHTML);

            // Update the button HTML
            directGmailAuthBtn.innerHTML = newButtonHTML;
            console.log('Button HTML updated');

            // Update button styling
            directGmailAuthBtn.classList.add('connected');

            // We no longer need to set onclick here since we have a global event listener
            // that handles both connected and disconnected states

            // Enable the destination connection button
            const connectDestinationBtn = document.getElementById('connectDestination');
            if (connectDestinationBtn) {
                connectDestinationBtn.disabled = false;
            }

            logToConsole('Updated Gmail auth button with user info', 'info');
        } catch (e) {
            console.error('Error updating Gmail auth button:', e);
        }
    } else {
        console.log('No Gmail token found, button not updated');
    }
}

// Function to disconnect from Gmail
function disconnectGmail() {
    // Clear tokens and user info
    localStorage.removeItem('gmailToken');
    localStorage.removeItem('gmailUserInfo');

    // Reset the button
    const directGmailAuthBtn = document.getElementById('directGmailAuthBtn');
    if (directGmailAuthBtn) {
        directGmailAuthBtn.innerHTML = `
            <div class="auth-button-content">
                <img src="https://www.gstatic.com/firebasejs/ui/2.0.0/images/auth/google.svg" alt="Google Logo" class="auth-button-icon">
                <span class="auth-button-text">Sign in with Google</span>
            </div>
        `;
        directGmailAuthBtn.classList.remove('connected');
        // We no longer need to set onclick here since we have a global event listener
    }

    // Disable the destination connection button
    const connectDestinationBtn = document.getElementById('connectDestination');
    if (connectDestinationBtn) {
        connectDestinationBtn.disabled = true;
    }

    // Update state
    isGmailConnected = false;

    logToConsole('Disconnected from Gmail', 'info');
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
    console.log('Initializing application');

    // Check if we have a Gmail token
    const gmailToken = localStorage.getItem('gmailToken');
    console.log('Token in localStorage:', !!gmailToken);
    if (gmailToken) {
        console.log('Found gmail token:', gmailToken.substring(0, 10) + '...');

        // Also log any user info we have
        const userInfoString = localStorage.getItem('gmailUserInfo');
        console.log('User info in localStorage:', !!userInfoString);
        if (userInfoString) {
            try {
                const userInfo = JSON.parse(userInfoString);
                console.log('User info parsed:', userInfo);
            } catch (e) {
                console.error('Failed to parse user info:', e);
            }
        }
    }

    // Update UI based on authentication status
    updateUIBasedOnAuthentication();

    console.log('Application initialization complete');
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
