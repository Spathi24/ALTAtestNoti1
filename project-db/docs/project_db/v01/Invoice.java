/*PLEASE DO NOT EDIT THIS CODE*/
/*This code was generated using the UMPLE 1.37.0.8623.1cd95c4b0 modeling language!*/

package project_db.v01;
import java.sql.Date;
import java.util.*;

/**
 * -----------------------------------------------------------------------------
 * Finance (minimal in v0.1 — full P&L comes in full model)
 * -----------------------------------------------------------------------------
 * Note: Invoice is intentionally NOT a composition of Project. Financial
 * records must survive operational deletions (compliance / audit).
 */
// line 267 "../../model-v0.1.ump"
public class Invoice extends CanonicalEntity
{

  //------------------------
  // ENUMERATIONS
  //------------------------

  public enum InvoiceStatus { DRAFT, SENT, PARTIAL, PAID, OVERDUE, VOID }

  //------------------------
  // MEMBER VARIABLES
  //------------------------

  //Invoice Attributes
  private String number;
  private Decimal amount;
  private Date issueDate;
  private Date dueDate;
  private InvoiceStatus status;

  //Invoice Associations
  private Project project;
  private Client client;

  //------------------------
  // CONSTRUCTOR
  //------------------------

  public Invoice(UUID aCanonicalId, DateTime aCreatedAt, DateTime aUpdatedAt, String aNumber, Decimal aAmount, Date aIssueDate, InvoiceStatus aStatus, Project aProject, Client aClient)
  {
    super(aCanonicalId, aCreatedAt, aUpdatedAt);
    number = aNumber;
    amount = aAmount;
    issueDate = aIssueDate;
    dueDate = null;
    status = aStatus;
    boolean didAddProject = setProject(aProject);
    if (!didAddProject)
    {
      throw new RuntimeException("Unable to create invoice due to project. See https://manual.umple.org?RE002ViolationofAssociationMultiplicity.html");
    }
    boolean didAddClient = setClient(aClient);
    if (!didAddClient)
    {
      throw new RuntimeException("Unable to create invoice due to client. See https://manual.umple.org?RE002ViolationofAssociationMultiplicity.html");
    }
  }

  //------------------------
  // INTERFACE
  //------------------------

  public boolean setAmount(Decimal aAmount)
  {
    boolean wasSet = false;
    amount = aAmount;
    wasSet = true;
    return wasSet;
  }

  public boolean setDueDate(Date aDueDate)
  {
    boolean wasSet = false;
    dueDate = aDueDate;
    wasSet = true;
    return wasSet;
  }

  public boolean setStatus(InvoiceStatus aStatus)
  {
    boolean wasSet = false;
    status = aStatus;
    wasSet = true;
    return wasSet;
  }

  public String getNumber()
  {
    return number;
  }

  public Decimal getAmount()
  {
    return amount;
  }

  public Date getIssueDate()
  {
    return issueDate;
  }

  public Date getDueDate()
  {
    return dueDate;
  }

  public InvoiceStatus getStatus()
  {
    return status;
  }
  /* Code from template association_GetOne */
  public Project getProject()
  {
    return project;
  }
  /* Code from template association_GetOne */
  public Client getClient()
  {
    return client;
  }
  /* Code from template association_SetOneToMany */
  public boolean setProject(Project aProject)
  {
    boolean wasSet = false;
    if (aProject == null)
    {
      return wasSet;
    }

    Project existingProject = project;
    project = aProject;
    if (existingProject != null && !existingProject.equals(aProject))
    {
      existingProject.removeInvoice(this);
    }
    project.addInvoice(this);
    wasSet = true;
    return wasSet;
  }
  /* Code from template association_SetOneToMany */
  public boolean setClient(Client aClient)
  {
    boolean wasSet = false;
    if (aClient == null)
    {
      return wasSet;
    }

    Client existingClient = client;
    client = aClient;
    if (existingClient != null && !existingClient.equals(aClient))
    {
      existingClient.removeInvoice(this);
    }
    client.addInvoice(this);
    wasSet = true;
    return wasSet;
  }

  public void delete()
  {
    Project placeholderProject = project;
    this.project = null;
    if(placeholderProject != null)
    {
      placeholderProject.removeInvoice(this);
    }
    Client placeholderClient = client;
    this.client = null;
    if(placeholderClient != null)
    {
      placeholderClient.removeInvoice(this);
    }
    super.delete();
  }


  public String toString()
  {
    return super.toString() + "["+
            "number" + ":" + getNumber()+ "]" + System.getProperties().getProperty("line.separator") +
            "  " + "amount" + "=" + (getAmount() != null ? !getAmount().equals(this)  ? getAmount().toString().replaceAll("  ","    ") : "this" : "null") + System.getProperties().getProperty("line.separator") +
            "  " + "issueDate" + "=" + (getIssueDate() != null ? !getIssueDate().equals(this)  ? getIssueDate().toString().replaceAll("  ","    ") : "this" : "null") + System.getProperties().getProperty("line.separator") +
            "  " + "dueDate" + "=" + (getDueDate() != null ? !getDueDate().equals(this)  ? getDueDate().toString().replaceAll("  ","    ") : "this" : "null") + System.getProperties().getProperty("line.separator") +
            "  " + "status" + "=" + (getStatus() != null ? !getStatus().equals(this)  ? getStatus().toString().replaceAll("  ","    ") : "this" : "null") + System.getProperties().getProperty("line.separator") +
            "  " + "project = "+(getProject()!=null?Integer.toHexString(System.identityHashCode(getProject())):"null") + System.getProperties().getProperty("line.separator") +
            "  " + "client = "+(getClient()!=null?Integer.toHexString(System.identityHashCode(getClient())):"null");
  }
}