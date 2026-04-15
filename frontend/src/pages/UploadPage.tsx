import { Link } from "react-router-dom";

function UploadPage() {
  return (
    <div className="page">
      <div className="uploads-disabled">
        <h1>Uploads Disabled</h1>
        <p>
          This project has been abandoned and uploads are no longer accepted.
        </p>
        <p>
          The domain is for sale — contact{" "}
          <a href="mailto:info@crossfirelab.com">info@crossfirelab.com</a>.
        </p>
        <Link to="/" className="btn btn-primary" style={{ marginTop: "1rem" }}>
          Back to Home
        </Link>
      </div>
    </div>
  );
}

export default UploadPage;
