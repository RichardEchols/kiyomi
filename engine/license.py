#!/usr/bin/env python3
"""
Kiyomi License Validation System
Validates Gumroad license keys and manages activation.
"""
import json
import urllib.request
import urllib.parse
import subprocess
import datetime
import os
import sys
from pathlib import Path

# License file location
LICENSE_DIR = Path.home() / ".kiyomi"
LICENSE_FILE = LICENSE_DIR / "license.json"


def get_machine_uuid():
    """Get machine's hardware UUID using system_profiler."""
    try:
        result = subprocess.run(
            ["system_profiler", "SPHardwareDataType"],
            capture_output=True,
            text=True,
            check=True
        )
        
        for line in result.stdout.split('\n'):
            if 'UUID' in line:
                parts = line.split()
                if len(parts) >= 3:
                    return parts[2].strip()
        
        # Fallback: use system hostname + username
        import socket
        import getpass
        return f"{socket.gethostname()}-{getpass.getuser()}"
        
    except Exception:
        # Final fallback
        import socket
        import getpass
        return f"{socket.gethostname()}-{getpass.getuser()}"


def validate_license_key(license_key, instance_name, increment_uses=False):
    """Validate license key against Gumroad API.

    Args:
        license_key: The license key to validate.
        instance_name: Machine identifier for tracking.
        increment_uses: If True, increment the uses count (only on first activation).
    """
    # Gumroad product IDs (permalinks) for different tiers
    product_ids = [
        "fgiwh",           # Monthly
        "kiyomi-lifetime", # Lifetime
        "kiyomi-agency"    # Agency
    ]

    for product_id in product_ids:
        try:
            # Prepare form data
            data = {
                'product_id': product_id,
                'license_key': license_key,
            }
            if increment_uses:
                data['increment_uses_count'] = 'true'

            # Encode form data
            encoded_data = urllib.parse.urlencode(data).encode('utf-8')

            # Create request
            req = urllib.request.Request(
                'https://api.gumroad.com/v2/licenses/verify',
                data=encoded_data,
                headers={
                    'Content-Type': 'application/x-www-form-urlencoded',
                }
            )

            # Send request
            with urllib.request.urlopen(req, timeout=10) as response:
                if response.status == 200:
                    result = json.loads(response.read().decode('utf-8'))
                    if result.get('success', False):
                        # Found valid license for this product
                        return True, {
                            'product_id': product_id,
                            'license_data': result,
                            'purchase_info': result.get('purchase', {}),
                            'uses': result.get('uses', 0)
                        }

        except Exception as e:
            # Try next product ID
            continue

    # No valid license found for any product
    return False, "License key not found or invalid"


def activate_license(license_key, instance_name):
    """Activate a license key (increments Gumroad uses count)."""
    return validate_license_key(license_key, instance_name, increment_uses=True)


def load_license():
    """Load license from local file."""
    try:
        if not LICENSE_FILE.exists():
            return None
            
        with open(LICENSE_FILE, 'r') as f:
            return json.load(f)
    except Exception:
        return None


def save_license(license_key, instance_id, validation_result):
    """Save validated license to local file."""
    try:
        # Ensure license directory exists
        LICENSE_DIR.mkdir(parents=True, exist_ok=True)

        # Extract product info from Gumroad response
        product_id = validation_result.get('product_id', 'kiyomi')
        purchase_info = validation_result.get('purchase_info', {})
        product_name = purchase_info.get('product_name', 'Kiyomi')

        # Map product IDs to friendly names
        product_names = {
            'fgiwh': 'Kiyomi Monthly',
            'kiyomi-lifetime': 'Kiyomi Lifetime',
            'kiyomi-agency': 'Kiyomi Agency'
        }
        display_name = product_names.get(product_id, product_name)

        license_data = {
            "key": license_key,
            "instance_id": instance_id,
            "validated_at": datetime.datetime.now().isoformat(),
            "product_name": display_name,
            "product_id": product_id,
            "purchase_info": purchase_info,
            "uses": validation_result.get('uses', 0)
        }
        
        with open(LICENSE_FILE, 'w') as f:
            json.dump(license_data, f, indent=2)
            
        return True
    except Exception as e:
        print(f"Error saving license: {e}")
        return False


def quick_revalidate(license_key, instance_name):
    """Quick revalidation with grace period."""
    license_data = load_license()
    if not license_data:
        return False
    
    # Check if we have a recent validation (within 7 days)
    try:
        validated_at = datetime.datetime.fromisoformat(license_data['validated_at'])
        days_since = (datetime.datetime.now() - validated_at).days
        
        if days_since <= 7:
            # Within grace period - try quick validation, but allow offline
            try:
                valid, _ = validate_license_key(license_key, instance_name)
                if valid:
                    # Update validation timestamp
                    license_data['validated_at'] = datetime.datetime.now().isoformat()
                    with open(LICENSE_FILE, 'w') as f:
                        json.dump(license_data, f, indent=2)
                return True  # Accept even if API is down during grace period
            except:
                return True  # Grace period - allow offline usage
        else:
            # Grace period expired - must validate online
            valid, _ = validate_license_key(license_key, instance_name)
            if valid:
                # Update validation timestamp
                license_data['validated_at'] = datetime.datetime.now().isoformat()
                with open(LICENSE_FILE, 'w') as f:
                    json.dump(license_data, f, indent=2)
                return True
            return False
            
    except Exception:
        return False


def prompt_for_license():
    """Prompt user for license key."""
    print("\n🌸 Welcome to Kiyomi!")
    print("To continue, please enter your license key.")
    print("(You can purchase one at: https://kiyomibot.ai)")
    
    while True:
        license_key = input("\nEnter your license key: ").strip()
        if license_key:
            return license_key
        print("Please enter a valid license key.")


def check_license():
    """
    Main license check function.
    Returns True if license is valid, False otherwise.
    """
    try:
        # Check if license file exists
        license_data = load_license()
        machine_uuid = get_machine_uuid()
        
        if license_data:
            # License exists - do quick revalidation
            license_key = license_data.get('key', '')
            if license_key and quick_revalidate(license_key, machine_uuid):
                return True
            else:
                # Revalidation failed - remove invalid license
                try:
                    LICENSE_FILE.unlink()
                except:
                    pass
        
        # No valid license - prompt for new one
        license_key = prompt_for_license()
        
        print("\nValidating license key...")
        
        # Validate the key
        valid, result = validate_license_key(license_key, machine_uuid)
        if not valid:
            print(f"License validation failed: {result}")
            print("Please purchase Kiyomi at https://kiyomibot.ai")
            return False
        
        print("License key is valid! Activating...")

        # Activate (increments Gumroad uses count once)
        activated, activation_result = activate_license(license_key, machine_uuid)
        if not activated:
            print(f"License activation failed: {activation_result}")
            print("Please contact support or try again.")
            return False

        # Save the license
        if save_license(license_key, machine_uuid, activation_result):
            # Get friendly product name
            product_names = {
                'fgiwh': 'Kiyomi Monthly',
                'kiyomi-lifetime': 'Kiyomi Lifetime',
                'kiyomi-agency': 'Kiyomi Agency'
            }
            product_id = activation_result.get('product_id', '')
            display_name = product_names.get(product_id, 'Kiyomi')
            
            print(f"✅ License activated successfully! Welcome to {display_name}.")
            return True
        else:
            print("Error saving license. Please try again.")
            return False
            
    except KeyboardInterrupt:
        print("\nLicense check cancelled.")
        return False
    except Exception as e:
        print(f"License check error: {e}")
        print("Please purchase Kiyomi at https://kiyomibot.ai")
        return False


if __name__ == "__main__":
    # Test the license system
    if check_license():
        print("License check passed!")
    else:
        print("License check failed!")
        sys.exit(1)