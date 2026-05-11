/*PLEASE DO NOT EDIT THIS CODE*/
/*This code was generated using the UMPLE 1.37.0.8623.1cd95c4b0 modeling language!*/

package project_db.v01;
import java.sql.Date;
import java.util.*;

/**
 * -----------------------------------------------------------------------------
 * Delivery
 * -----------------------------------------------------------------------------
 * A Deal can spawn multiple Projects (phased contracts), so Project — Deal
 * stays * -- 0..1 deliberately.
 */
// line 222 "../../model-v0.1.ump"
public class Project extends CanonicalEntity
{

  //------------------------
  // ENUMERATIONS
  //------------------------

  public enum ProjectStatus { PROPOSED, ACTIVE, ON_HOLD, COMPLETED, CANCELLED }
  public enum InvoiceStatus { DRAFT, SENT, PARTIAL, PAID, OVERDUE, VOID }
  public enum TaskStatus { TODO, IN_PROGRESS, BLOCKED, DONE, CANCELLED }

  //------------------------
  // MEMBER VARIABLES
  //------------------------

  //Project Attributes
  private String name;
  private String code;
  private ProjectStatus status;
  private Date startDate;
  private Date endDate;
  private Decimal budgetAmount;
  private Decimal contractAmount;

  //Project Associations
  private Client client;
  private Deal deal;
  private Property property;
  private User projectManager;
  private List<Task> tasks;
  private List<DailyLog> dailyLogs;
  private List<Invoice> invoices;
  private List<Document> documents;

  //------------------------
  // CONSTRUCTOR
  //------------------------

  public Project(UUID aCanonicalId, DateTime aCreatedAt, DateTime aUpdatedAt, String aName, ProjectStatus aStatus, Client aClient)
  {
    super(aCanonicalId, aCreatedAt, aUpdatedAt);
    name = aName;
    code = null;
    status = aStatus;
    startDate = null;
    endDate = null;
    boolean didAddClient = setClient(aClient);
    if (!didAddClient)
    {
      throw new RuntimeException("Unable to create project due to client. See https://manual.umple.org?RE002ViolationofAssociationMultiplicity.html");
    }
    tasks = new ArrayList<Task>();
    dailyLogs = new ArrayList<DailyLog>();
    invoices = new ArrayList<Invoice>();
    documents = new ArrayList<Document>();
  }

  //------------------------
  // INTERFACE
  //------------------------

  public boolean setName(String aName)
  {
    boolean wasSet = false;
    name = aName;
    wasSet = true;
    return wasSet;
  }

  public boolean setCode(String aCode)
  {
    boolean wasSet = false;
    code = aCode;
    wasSet = true;
    return wasSet;
  }

  public boolean setStatus(ProjectStatus aStatus)
  {
    boolean wasSet = false;
    status = aStatus;
    wasSet = true;
    return wasSet;
  }

  public boolean setStartDate(Date aStartDate)
  {
    boolean wasSet = false;
    startDate = aStartDate;
    wasSet = true;
    return wasSet;
  }

  public boolean setEndDate(Date aEndDate)
  {
    boolean wasSet = false;
    endDate = aEndDate;
    wasSet = true;
    return wasSet;
  }

  public boolean setBudgetAmount(Decimal aBudgetAmount)
  {
    boolean wasSet = false;
    budgetAmount = aBudgetAmount;
    wasSet = true;
    return wasSet;
  }

  public boolean setContractAmount(Decimal aContractAmount)
  {
    boolean wasSet = false;
    contractAmount = aContractAmount;
    wasSet = true;
    return wasSet;
  }

  public String getName()
  {
    return name;
  }

  /**
   * human-readable e.g. "923-ROCK-001"
   */
  public String getCode()
  {
    return code;
  }

  public ProjectStatus getStatus()
  {
    return status;
  }

  public Date getStartDate()
  {
    return startDate;
  }

  public Date getEndDate()
  {
    return endDate;
  }

  public Decimal getBudgetAmount()
  {
    return budgetAmount;
  }

  public Decimal getContractAmount()
  {
    return contractAmount;
  }
  /* Code from template association_GetOne */
  public Client getClient()
  {
    return client;
  }
  /* Code from template association_GetOne */
  public Deal getDeal()
  {
    return deal;
  }

  public boolean hasDeal()
  {
    boolean has = deal != null;
    return has;
  }
  /* Code from template association_GetOne */
  public Property getProperty()
  {
    return property;
  }

  public boolean hasProperty()
  {
    boolean has = property != null;
    return has;
  }
  /* Code from template association_GetOne */
  public User getProjectManager()
  {
    return projectManager;
  }

  public boolean hasProjectManager()
  {
    boolean has = projectManager != null;
    return has;
  }
  /* Code from template association_GetMany */
  public Task getTask(int index)
  {
    Task aTask = tasks.get(index);
    return aTask;
  }

  public List<Task> getTasks()
  {
    List<Task> newTasks = Collections.unmodifiableList(tasks);
    return newTasks;
  }

  public int numberOfTasks()
  {
    int number = tasks.size();
    return number;
  }

  public boolean hasTasks()
  {
    boolean has = tasks.size() > 0;
    return has;
  }

  public int indexOfTask(Task aTask)
  {
    int index = tasks.indexOf(aTask);
    return index;
  }
  /* Code from template association_GetMany */
  public DailyLog getDailyLog(int index)
  {
    DailyLog aDailyLog = dailyLogs.get(index);
    return aDailyLog;
  }

  public List<DailyLog> getDailyLogs()
  {
    List<DailyLog> newDailyLogs = Collections.unmodifiableList(dailyLogs);
    return newDailyLogs;
  }

  public int numberOfDailyLogs()
  {
    int number = dailyLogs.size();
    return number;
  }

  public boolean hasDailyLogs()
  {
    boolean has = dailyLogs.size() > 0;
    return has;
  }

  public int indexOfDailyLog(DailyLog aDailyLog)
  {
    int index = dailyLogs.indexOf(aDailyLog);
    return index;
  }
  /* Code from template association_GetMany */
  public Invoice getInvoice(int index)
  {
    Invoice aInvoice = invoices.get(index);
    return aInvoice;
  }

  public List<Invoice> getInvoices()
  {
    List<Invoice> newInvoices = Collections.unmodifiableList(invoices);
    return newInvoices;
  }

  public int numberOfInvoices()
  {
    int number = invoices.size();
    return number;
  }

  public boolean hasInvoices()
  {
    boolean has = invoices.size() > 0;
    return has;
  }

  public int indexOfInvoice(Invoice aInvoice)
  {
    int index = invoices.indexOf(aInvoice);
    return index;
  }
  /* Code from template association_GetMany */
  public Document getDocument(int index)
  {
    Document aDocument = documents.get(index);
    return aDocument;
  }

  public List<Document> getDocuments()
  {
    List<Document> newDocuments = Collections.unmodifiableList(documents);
    return newDocuments;
  }

  public int numberOfDocuments()
  {
    int number = documents.size();
    return number;
  }

  public boolean hasDocuments()
  {
    boolean has = documents.size() > 0;
    return has;
  }

  public int indexOfDocument(Document aDocument)
  {
    int index = documents.indexOf(aDocument);
    return index;
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
      existingClient.removeProject(this);
    }
    client.addProject(this);
    wasSet = true;
    return wasSet;
  }
  /* Code from template association_SetOptionalOneToMany */
  public boolean setDeal(Deal aDeal)
  {
    boolean wasSet = false;
    Deal existingDeal = deal;
    deal = aDeal;
    if (existingDeal != null && !existingDeal.equals(aDeal))
    {
      existingDeal.removeProject(this);
    }
    if (aDeal != null)
    {
      aDeal.addProject(this);
    }
    wasSet = true;
    return wasSet;
  }
  /* Code from template association_SetOptionalOneToMany */
  public boolean setProperty(Property aProperty)
  {
    boolean wasSet = false;
    Property existingProperty = property;
    property = aProperty;
    if (existingProperty != null && !existingProperty.equals(aProperty))
    {
      existingProperty.removeProject(this);
    }
    if (aProperty != null)
    {
      aProperty.addProject(this);
    }
    wasSet = true;
    return wasSet;
  }
  /* Code from template association_SetOptionalOneToMany */
  public boolean setProjectManager(User aProjectManager)
  {
    boolean wasSet = false;
    User existingProjectManager = projectManager;
    projectManager = aProjectManager;
    if (existingProjectManager != null && !existingProjectManager.equals(aProjectManager))
    {
      existingProjectManager.removeProject(this);
    }
    if (aProjectManager != null)
    {
      aProjectManager.addProject(this);
    }
    wasSet = true;
    return wasSet;
  }
  /* Code from template association_MinimumNumberOfMethod */
  public static int minimumNumberOfTasks()
  {
    return 0;
  }
  /* Code from template association_AddManyToOne */
  public Task addTask(UUID aCanonicalId, DateTime aCreatedAt, DateTime aUpdatedAt, String aTitle, TaskStatus aStatus)
  {
    return new Task(aCanonicalId, aCreatedAt, aUpdatedAt, aTitle, aStatus, this);
  }

  public boolean addTask(Task aTask)
  {
    boolean wasAdded = false;
    if (tasks.contains(aTask)) { return false; }
    Project existingProject = aTask.getProject();
    boolean isNewProject = existingProject != null && !this.equals(existingProject);
    if (isNewProject)
    {
      aTask.setProject(this);
    }
    else
    {
      tasks.add(aTask);
    }
    wasAdded = true;
    return wasAdded;
  }

  public boolean removeTask(Task aTask)
  {
    boolean wasRemoved = false;
    //Unable to remove aTask, as it must always have a project
    if (!this.equals(aTask.getProject()))
    {
      tasks.remove(aTask);
      wasRemoved = true;
    }
    return wasRemoved;
  }
  /* Code from template association_AddIndexControlFunctions */
  public boolean addTaskAt(Task aTask, int index)
  {  
    boolean wasAdded = false;
    if(addTask(aTask))
    {
      if(index < 0 ) { index = 0; }
      if(index > numberOfTasks()) { index = numberOfTasks() - 1; }
      tasks.remove(aTask);
      tasks.add(index, aTask);
      wasAdded = true;
    }
    return wasAdded;
  }

  public boolean addOrMoveTaskAt(Task aTask, int index)
  {
    boolean wasAdded = false;
    if(tasks.contains(aTask))
    {
      if(index < 0 ) { index = 0; }
      if(index > numberOfTasks()) { index = numberOfTasks() - 1; }
      tasks.remove(aTask);
      tasks.add(index, aTask);
      wasAdded = true;
    } 
    else 
    {
      wasAdded = addTaskAt(aTask, index);
    }
    return wasAdded;
  }
  /* Code from template association_MinimumNumberOfMethod */
  public static int minimumNumberOfDailyLogs()
  {
    return 0;
  }
  /* Code from template association_AddManyToOne */
  public DailyLog addDailyLog(UUID aCanonicalId, DateTime aCreatedAt, DateTime aUpdatedAt, Date aLogDate)
  {
    return new DailyLog(aCanonicalId, aCreatedAt, aUpdatedAt, aLogDate, this);
  }

  public boolean addDailyLog(DailyLog aDailyLog)
  {
    boolean wasAdded = false;
    if (dailyLogs.contains(aDailyLog)) { return false; }
    Project existingProject = aDailyLog.getProject();
    boolean isNewProject = existingProject != null && !this.equals(existingProject);
    if (isNewProject)
    {
      aDailyLog.setProject(this);
    }
    else
    {
      dailyLogs.add(aDailyLog);
    }
    wasAdded = true;
    return wasAdded;
  }

  public boolean removeDailyLog(DailyLog aDailyLog)
  {
    boolean wasRemoved = false;
    //Unable to remove aDailyLog, as it must always have a project
    if (!this.equals(aDailyLog.getProject()))
    {
      dailyLogs.remove(aDailyLog);
      wasRemoved = true;
    }
    return wasRemoved;
  }
  /* Code from template association_AddIndexControlFunctions */
  public boolean addDailyLogAt(DailyLog aDailyLog, int index)
  {  
    boolean wasAdded = false;
    if(addDailyLog(aDailyLog))
    {
      if(index < 0 ) { index = 0; }
      if(index > numberOfDailyLogs()) { index = numberOfDailyLogs() - 1; }
      dailyLogs.remove(aDailyLog);
      dailyLogs.add(index, aDailyLog);
      wasAdded = true;
    }
    return wasAdded;
  }

  public boolean addOrMoveDailyLogAt(DailyLog aDailyLog, int index)
  {
    boolean wasAdded = false;
    if(dailyLogs.contains(aDailyLog))
    {
      if(index < 0 ) { index = 0; }
      if(index > numberOfDailyLogs()) { index = numberOfDailyLogs() - 1; }
      dailyLogs.remove(aDailyLog);
      dailyLogs.add(index, aDailyLog);
      wasAdded = true;
    } 
    else 
    {
      wasAdded = addDailyLogAt(aDailyLog, index);
    }
    return wasAdded;
  }
  /* Code from template association_MinimumNumberOfMethod */
  public static int minimumNumberOfInvoices()
  {
    return 0;
  }
  /* Code from template association_AddManyToOne */
  public Invoice addInvoice(UUID aCanonicalId, DateTime aCreatedAt, DateTime aUpdatedAt, String aNumber, Decimal aAmount, Date aIssueDate, InvoiceStatus aStatus, Client aClient)
  {
    return new Invoice(aCanonicalId, aCreatedAt, aUpdatedAt, aNumber, aAmount, aIssueDate, aStatus, this, aClient);
  }

  public boolean addInvoice(Invoice aInvoice)
  {
    boolean wasAdded = false;
    if (invoices.contains(aInvoice)) { return false; }
    Project existingProject = aInvoice.getProject();
    boolean isNewProject = existingProject != null && !this.equals(existingProject);
    if (isNewProject)
    {
      aInvoice.setProject(this);
    }
    else
    {
      invoices.add(aInvoice);
    }
    wasAdded = true;
    return wasAdded;
  }

  public boolean removeInvoice(Invoice aInvoice)
  {
    boolean wasRemoved = false;
    //Unable to remove aInvoice, as it must always have a project
    if (!this.equals(aInvoice.getProject()))
    {
      invoices.remove(aInvoice);
      wasRemoved = true;
    }
    return wasRemoved;
  }
  /* Code from template association_AddIndexControlFunctions */
  public boolean addInvoiceAt(Invoice aInvoice, int index)
  {  
    boolean wasAdded = false;
    if(addInvoice(aInvoice))
    {
      if(index < 0 ) { index = 0; }
      if(index > numberOfInvoices()) { index = numberOfInvoices() - 1; }
      invoices.remove(aInvoice);
      invoices.add(index, aInvoice);
      wasAdded = true;
    }
    return wasAdded;
  }

  public boolean addOrMoveInvoiceAt(Invoice aInvoice, int index)
  {
    boolean wasAdded = false;
    if(invoices.contains(aInvoice))
    {
      if(index < 0 ) { index = 0; }
      if(index > numberOfInvoices()) { index = numberOfInvoices() - 1; }
      invoices.remove(aInvoice);
      invoices.add(index, aInvoice);
      wasAdded = true;
    } 
    else 
    {
      wasAdded = addInvoiceAt(aInvoice, index);
    }
    return wasAdded;
  }
  /* Code from template association_MinimumNumberOfMethod */
  public static int minimumNumberOfDocuments()
  {
    return 0;
  }
  /* Code from template association_AddManyToOptionalOne */
  public boolean addDocument(Document aDocument)
  {
    boolean wasAdded = false;
    if (documents.contains(aDocument)) { return false; }
    Project existingProject = aDocument.getProject();
    if (existingProject == null)
    {
      aDocument.setProject(this);
    }
    else if (!this.equals(existingProject))
    {
      existingProject.removeDocument(aDocument);
      addDocument(aDocument);
    }
    else
    {
      documents.add(aDocument);
    }
    wasAdded = true;
    return wasAdded;
  }

  public boolean removeDocument(Document aDocument)
  {
    boolean wasRemoved = false;
    if (documents.contains(aDocument))
    {
      documents.remove(aDocument);
      aDocument.setProject(null);
      wasRemoved = true;
    }
    return wasRemoved;
  }
  /* Code from template association_AddIndexControlFunctions */
  public boolean addDocumentAt(Document aDocument, int index)
  {  
    boolean wasAdded = false;
    if(addDocument(aDocument))
    {
      if(index < 0 ) { index = 0; }
      if(index > numberOfDocuments()) { index = numberOfDocuments() - 1; }
      documents.remove(aDocument);
      documents.add(index, aDocument);
      wasAdded = true;
    }
    return wasAdded;
  }

  public boolean addOrMoveDocumentAt(Document aDocument, int index)
  {
    boolean wasAdded = false;
    if(documents.contains(aDocument))
    {
      if(index < 0 ) { index = 0; }
      if(index > numberOfDocuments()) { index = numberOfDocuments() - 1; }
      documents.remove(aDocument);
      documents.add(index, aDocument);
      wasAdded = true;
    } 
    else 
    {
      wasAdded = addDocumentAt(aDocument, index);
    }
    return wasAdded;
  }

  public void delete()
  {
    Client placeholderClient = client;
    this.client = null;
    if(placeholderClient != null)
    {
      placeholderClient.removeProject(this);
    }
    if (deal != null)
    {
      Deal placeholderDeal = deal;
      this.deal = null;
      placeholderDeal.removeProject(this);
    }
    if (property != null)
    {
      Property placeholderProperty = property;
      this.property = null;
      placeholderProperty.removeProject(this);
    }
    if (projectManager != null)
    {
      User placeholderProjectManager = projectManager;
      this.projectManager = null;
      placeholderProjectManager.removeProject(this);
    }
    while (tasks.size() > 0)
    {
      Task aTask = tasks.get(tasks.size() - 1);
      aTask.delete();
      tasks.remove(aTask);
    }
    
    while (dailyLogs.size() > 0)
    {
      DailyLog aDailyLog = dailyLogs.get(dailyLogs.size() - 1);
      aDailyLog.delete();
      dailyLogs.remove(aDailyLog);
    }
    
    for(int i=invoices.size(); i > 0; i--)
    {
      Invoice aInvoice = invoices.get(i - 1);
      aInvoice.delete();
    }
    while( !documents.isEmpty() )
    {
      documents.get(0).setProject(null);
    }
    super.delete();
  }


  public String toString()
  {
    return super.toString() + "["+
            "name" + ":" + getName()+ "," +
            "code" + ":" + getCode()+ "]" + System.getProperties().getProperty("line.separator") +
            "  " + "status" + "=" + (getStatus() != null ? !getStatus().equals(this)  ? getStatus().toString().replaceAll("  ","    ") : "this" : "null") + System.getProperties().getProperty("line.separator") +
            "  " + "startDate" + "=" + (getStartDate() != null ? !getStartDate().equals(this)  ? getStartDate().toString().replaceAll("  ","    ") : "this" : "null") + System.getProperties().getProperty("line.separator") +
            "  " + "endDate" + "=" + (getEndDate() != null ? !getEndDate().equals(this)  ? getEndDate().toString().replaceAll("  ","    ") : "this" : "null") + System.getProperties().getProperty("line.separator") +
            "  " + "budgetAmount" + "=" + (getBudgetAmount() != null ? !getBudgetAmount().equals(this)  ? getBudgetAmount().toString().replaceAll("  ","    ") : "this" : "null") + System.getProperties().getProperty("line.separator") +
            "  " + "contractAmount" + "=" + (getContractAmount() != null ? !getContractAmount().equals(this)  ? getContractAmount().toString().replaceAll("  ","    ") : "this" : "null") + System.getProperties().getProperty("line.separator") +
            "  " + "client = "+(getClient()!=null?Integer.toHexString(System.identityHashCode(getClient())):"null") + System.getProperties().getProperty("line.separator") +
            "  " + "deal = "+(getDeal()!=null?Integer.toHexString(System.identityHashCode(getDeal())):"null") + System.getProperties().getProperty("line.separator") +
            "  " + "property = "+(getProperty()!=null?Integer.toHexString(System.identityHashCode(getProperty())):"null") + System.getProperties().getProperty("line.separator") +
            "  " + "projectManager = "+(getProjectManager()!=null?Integer.toHexString(System.identityHashCode(getProjectManager())):"null");
  }
}