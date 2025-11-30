let uploadedPath = "";

document.getElementById('fileInput').addEventListener('change', async function(e) {
    const file = e.target.files[0];
    if(!file) return;

    document.getElementById('fileName').innerText = "Uploading: " + file.name;
    const formData = new FormData();
    formData.append('file', file);

    const res = await fetch('/api/upload', { method: 'POST', body: formData });
    const data = await res.json();
    uploadedPath = data.path;
    document.getElementById('fileName').innerText = "Uploaded ✅";
});

async function generateContent() {
    if(!uploadedPath) return alert("Please upload an image first");
    
    const platform = document.getElementById('platformSelect').value;
    const topic = document.getElementById('topicInput').value;

    // Show loading state...
    
    const res = await fetch('/api/generate', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ filepath: uploadedPath, platform: platform, topic: topic })
    });
    
    const data = await res.json();
    
    document.getElementById('previewImage').src = data.image_url;
    document.getElementById('previewCaption').value = data.caption;
    document.getElementById('previewCard').classList.remove('hidden');
}

async function schedulePost() {
    const platform = document.getElementById('platformSelect').value;
    const img = document.getElementById('previewImage').src;
    const caption = document.getElementById('previewCaption').value;

    const res = await fetch('/api/schedule', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ image_url: img, caption: caption, platform: platform })
    });

    const data = await res.json();
    alert(data.msg);
    window.location.href = '/'; // Go back to dashboard to see it in the table
}