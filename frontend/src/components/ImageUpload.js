import React, { useState } from "react";

export default function ImageUpload() {
  const [selectedFile, setSelectedFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);
  const [selectedLang, setSelectedLang] = useState("en");

  const onFileChange = (e) => {
    const file = e.target.files[0];
    setSelectedFile(file);
    setError("");
    setResult(null);

    if (file) {
      const url = URL.createObjectURL(file);
      setPreviewUrl(url);
    } else {
      setPreviewUrl(null);
    }
  };

  async function uploadImage(imageFile) {
    const formData = new FormData();
    formData.append("image", imageFile);

    const response = await fetch("http://localhost:5000/extract-text", {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Server error: ${response.status} ${errorText}`);
    }
    return response.json();
  }

  const onSubmit = async (e) => {
    e.preventDefault();

    if (!selectedFile) {
      setError("Please select an image file.");
      return;
    }

    setLoading(true);
    setError("");
    setResult(null);

    try {
      const response = await uploadImage(selectedFile);
      console.log("Backend response:", response);

      // Expecting response like { medicines: { en: [...], hi: [...], bn: [...] } }
      setResult(response);
    } catch (err) {
      setError(err.message || "Something went wrong.");
    } finally {
      setLoading(false);
    }
  };

  const displayValue = (value) =>
    value && value.trim() ? value : "Not enough data";

  return (
    <div
      style={{
        maxWidth: 800,
        margin: "40px auto",
        padding: 30,
        backgroundColor: "#fff",
        borderRadius: 12,
        boxShadow: "0 4px 20px rgba(0,0,0,0.1)",
      }}
    >
      <h2
        style={{
          textAlign: "center",
          marginBottom: 30,
          color: "#4a148c",
          fontWeight: "700",
        }}
      >
        Upload Medicine Image
      </h2>

      {previewUrl && (
        <div style={{ marginBottom: 20, textAlign: "center" }}>
          <img
            src={previewUrl}
            alt="Preview"
            style={{ maxWidth: "100%", maxHeight: 300, borderRadius: 12 }}
          />
        </div>
      )}

      <form onSubmit={onSubmit} style={{ textAlign: "center" }}>
        <input type="file" accept="image/*" onChange={onFileChange} />
        <br />
        <button type="submit" disabled={loading} style={{ marginTop: 20 }}>
          {loading ? "Processing..." : "Upload & Extract"}
        </button>
      </form>

      {error && <p style={{ color: "red", textAlign: "center" }}>{error}</p>}

      {result && result.medicines && (
        <>
          {/* Language selector */}
          <div style={{ marginTop: 20, textAlign: "center" }}>
            <label style={{ marginRight: 10 }}>Select Language:</label>
            <select
              value={selectedLang}
              onChange={(e) => setSelectedLang(e.target.value)}
              style={{ padding: 5 }}
            >
              {Object.keys(result.medicines).map((langCode) => (
                <option key={langCode} value={langCode}>
                  {langCode.toUpperCase()}
                </option>
              ))}
            </select>
          </div>

          {/* Table */}
          <div style={{ marginTop: 20 }}>
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead>
                <tr style={{ backgroundColor: "#e1bee7" }}>
                  <th>Name</th>
                  <th>Dosage</th>
                  <th>Usage Instructions</th>
                  <th>Medicine Use</th>
                </tr>
              </thead>
              <tbody>
                {result.medicines[selectedLang]?.map((med, idx) => (
                  <tr
                    key={idx}
                    style={{
                      backgroundColor: idx % 2 === 0 ? "#f8f5fc" : "#fff",
                    }}
                  >
                    <td>{displayValue(med.medicine_name)}</td>
                    <td>{displayValue(med.dosage)}</td>
                    <td>{displayValue(med.usage_instructions)}</td>
                    <td>{displayValue(med.medicine_use)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
