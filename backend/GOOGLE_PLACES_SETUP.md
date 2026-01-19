# Google Places API Setup Guide

## Step 1: Get Your API Key

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Select your project (or create a new one)
3. Navigate to **APIs & Services** → **Credentials**
4. Click **Create Credentials** → **API Key**
5. Copy your API key

## Step 2: Enable Places API (New)

1. Go to **APIs & Services** → **Library**
2. Search for "Places API (New)"
3. Click on it and click **Enable**

**Important:** Make sure you enable "Places API (New)", not the old "Places API"

## Step 3: Configure Your API Key

Add your API key to your `.env` file in the project root:

```bash
GOOGLE_PLACES_API_KEY=your_api_key_here
```

Or set it as an environment variable:

```bash
export GOOGLE_PLACES_API_KEY=your_api_key_here
```

## Step 4: Restrict Your API Key (Recommended for Production)

1. Go to **APIs & Services** → **Credentials**
2. Click on your API key
3. Under **API restrictions**, select **Restrict key**
4. Choose **Places API (New)** only
5. Under **Application restrictions**, you can restrict by IP or HTTP referrer

## Step 5: Test the Integration

Start your API server:

```bash
cd backend
uvicorn app.main:app --reload
```

Test the endpoint:

```bash
# Test with default location (San Francisco)
curl http://localhost:8000/test/google-places

# Test with custom location
curl "http://localhost:8000/test/google-places?lat=40.7128&lng=-74.0060&radius=2000"
```

## Troubleshooting

### Error: "Google Places API key is required"
- Make sure `GOOGLE_PLACES_API_KEY` is set in your `.env` file
- Restart your server after adding the key

### Error: "API key not valid"
- Verify the API key is correct
- Make sure Places API (New) is enabled
- Check if there are any restrictions on the API key

### Error: "Quota exceeded"
- Check your Google Cloud billing
- Verify you haven't exceeded the free tier limits

## API Usage Notes

- The Places API (New) has different pricing than the old API
- Free tier: $200 credit per month (covers ~40,000 requests)
- Each `searchNearby` request costs approximately $0.005
- See [Google Places API Pricing](https://mapsplatform.google.com/pricing/) for details
