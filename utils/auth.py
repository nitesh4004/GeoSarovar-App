import streamlit as st
import ee
import json

def authenticate_gee():
    try:
        # 1. Service Account (Secrets)
        if "gcp_service_account" in st.secrets:
            try:
                service_account = st.secrets["gcp_service_account"]["client_email"]
                secret_dict = dict(st.secrets["gcp_service_account"])
                key_data = json.dumps(secret_dict)
                credentials = ee.ServiceAccountCredentials(service_account, key_data=key_data)
                ee.Initialize(credentials)
                # If successful, we don't have a specific project ID variable from secrets easily unless we parse it,
                # but 'project_id' is usually in the secret dict.
                project_id = st.secrets["gcp_service_account"].get("project_id", "Service Account")
                st.session_state['active_project'] = project_id
                return
            except Exception as e:
                # If secrets fail, continue to local flow? Or stop? usually secrets are definitive.
                print(f"Secret Auth Failed: {e}")
                pass 

        # 2. Local Flow
        # Prioritize known working project
        target_project = 'ee-niteshgulzar'
        try: 
            ee.Initialize(project=target_project)
            st.session_state['active_project'] = target_project
        except Exception as e:
            # If specific project fails, check if we should prompt user
            if "no project found" in str(e) or "project" in str(e).lower() or "permission" in str(e).lower():
                st.warning(f"⚠️ Could not auto-connect to `{target_project}`.")
                project_id = st.text_input(
                    "Enter your Google Cloud Project ID:", 
                    value=target_project,
                    help="The ID of the GCP project with Earth Engine API enabled."
                )
                if project_id:
                    try:
                        ee.Initialize(project=project_id)
                        st.session_state['active_project'] = project_id
                        st.success(f"Successfully authenticated with project: {project_id}")
                    except Exception as e2:
                        st.error(f"Failed to connect with project ID '{project_id}': {e2}")
                        st.stop()
                else:
                    st.stop()
            else:
                # Last resort: Try generic init (might use default gcloud project)
                try:
                    ee.Initialize()
                    st.session_state['active_project'] = 'Default (Local)'
                except:
                    raise e
    except Exception as e:
        st.error(f"⚠️ GEE Authentication Error: {e}")
        st.info("If running locally, run `earthengine authenticate` in your terminal. If on Cloud, add secrets.")
        st.stop()
