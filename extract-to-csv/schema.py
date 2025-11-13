from pydantic import BaseModel, Field
from typing import List, Optional


class GrantData(BaseModel):

    grant_id: str = Field(description="Unique identifier for the grant. (e.g., GOVYUKON-EDF-T1-2025)")
    title: str = Field(description="The full, official title of the grant program.")
    description: str = Field(description="Crucial for AI. The full, detailed description from the source. The richer, the better for semantic matching.")
    funder: str = Field(description="The name of the government body, foundation, or corporation offering the grant.")
    funder_type: str = Field(description="(Canadian Context) The type of funder (e.g., Federal Grant, Provincial Grant, Municipal Grant, Foundation Grant, Corporate Grant).")
    funding_type: str = Field(description="Nature of the funding (e.g., 'Grant', 'Loan', 'Tax Credit').")
    amount_min: Optional[int] = Field(None, description="Minimum funding amount (in CENTS or smallest currency unit). Use None if not specified.")
    amount_max: Optional[int] = Field(None, description="Maximum funding amount (in CENTS or smallest currency unit). Use None if not specified.")
    currency: str = Field(description="The three-letter currency code (e.g., 'CAD', 'USD').")
    deadline: str = Field(description="The application deadline, formatted as 'YYYY-MM-DD' or a descriptive phrase if a date isn't available (e.g., 'Ongoing').")
    application_complexity: str = Field(description="Estimated complexity (e.g., 'Low', 'Medium', 'High').")
    eligible_provinces: List[str] = Field(description="List of eligible provinces/states/regions. Use ['National'] if nationwide.")
    geography_details: str = Field(description="Any specific local or regional restrictions not covered by provinces.")
    eligible_applicant_type: List[str] = Field(description="(Crucial for matching) List of organization types that can apply (e.g., 'Small Business', 'Non-profit', 'Individual').")
    eligible_industries: List[str] = Field(description="(Crucial for matching) List of specific industries or sectors targeted.")
    target_beneficiaries: List[str] = Field(description="(Crucial for matching) List of groups the grant is intended to support (e.g., 'Youth', 'Women-owned businesses').")
    supported_project_types: List[str] = Field(description="List of projects the grant can fund (e.g., 'R&D', 'Equipment Purchase', 'Training').")
    sdg_alignment: List[str] = Field(description="List of UN Sustainable Development Goals the grant aligns with.")
    application_url: str = Field(description="Direct URL to the application page or program details.")
    is_recurring: bool = Field(description="True if the grant is offered on a regular cycle (e.g., annually), False otherwise.")
    notes: str = Field(description="Any essential caveats or additional information.")
    