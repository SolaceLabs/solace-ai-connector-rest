import requests
import os

def test_stream_response():
    # API endpoint
    url = "http://127.0.0.1:5050/api/v1/request"
    #url = "https://solacechatbeta.mymaas.net/api/v1/request"
    
    token = os.getenv("TOKEN")
    # Request headers
    headers = {
        "Authorization": f"Bearer {token}"
        # Content-Type will be set automatically by requests for multipart/form-data
    }
    
    # Form data
    files = {
        # 'prompt': (None, "Create an image of a dog and a crocodile playing cards"),
        'prompt': (None, "Create an svg file of a circle in a square"),
        #'prompt': (None, "Create a csv with numbers 1 to 10?"),
        #'prompt': (None, "Determine my email address (greg.meldrum@solace.com). Then use it to find the peers in my group, then plot our locations on a map."),
        'stream': (None, 'true')
    }
    
    # Make POST request with stream=True and form data
    response = requests.post(url, files=files, headers=headers, stream=True)
    
    print(response)
    # Check response status
    assert response.status_code == 200
    
    # Counter to verify we receive some data
    chunks_received = 0
    
    # Read streaming response
    for chunk in response.iter_content(chunk_size=None, decode_unicode=True):
        if chunk:
            print(chunk, end='', flush=True)
            chunks_received += 1
            
            # Verify chunk is string data
            assert isinstance(chunk, str)
    
    # Verify we received some data
    assert chunks_received > 0
    
    # Verify response completed
    assert response.raw.closed == True

# If the user is calling the test_stream_response function, run the test
if __name__ == "__main__":
    test_stream_response()