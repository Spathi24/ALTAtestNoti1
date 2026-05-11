/*PLEASE DO NOT EDIT THIS CODE*/
/*This code was generated using the UMPLE 1.37.0.8623.1cd95c4b0 modeling language!*/

package project_db.v01;
import java.util.*;

/**
 * -----------------------------------------------------------------------------
 * Org / people
 * -----------------------------------------------------------------------------
 */
// line 134 "../../model-v0.1.ump"
public class Organization extends CanonicalEntity
{

  //------------------------
  // MEMBER VARIABLES
  //------------------------

  //Organization Attributes
  private String name;
  private String legalName;
  private String defaultCurrency;

  //Organization Associations
  private List<User> users;
  private List<Client> clients;
  private List<Vendor> vendors;
  private List<Property> properties;

  //------------------------
  // CONSTRUCTOR
  //------------------------

  public Organization(UUID aCanonicalId, DateTime aCreatedAt, DateTime aUpdatedAt, String aName)
  {
    super(aCanonicalId, aCreatedAt, aUpdatedAt);
    name = aName;
    legalName = null;
    defaultCurrency = null;
    users = new ArrayList<User>();
    clients = new ArrayList<Client>();
    vendors = new ArrayList<Vendor>();
    properties = new ArrayList<Property>();
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

  public boolean setLegalName(String aLegalName)
  {
    boolean wasSet = false;
    legalName = aLegalName;
    wasSet = true;
    return wasSet;
  }

  public boolean setDefaultCurrency(String aDefaultCurrency)
  {
    boolean wasSet = false;
    defaultCurrency = aDefaultCurrency;
    wasSet = true;
    return wasSet;
  }

  public String getName()
  {
    return name;
  }

  public String getLegalName()
  {
    return legalName;
  }

  public String getDefaultCurrency()
  {
    return defaultCurrency;
  }
  /* Code from template association_GetMany */
  public User getUser(int index)
  {
    User aUser = users.get(index);
    return aUser;
  }

  public List<User> getUsers()
  {
    List<User> newUsers = Collections.unmodifiableList(users);
    return newUsers;
  }

  public int numberOfUsers()
  {
    int number = users.size();
    return number;
  }

  public boolean hasUsers()
  {
    boolean has = users.size() > 0;
    return has;
  }

  public int indexOfUser(User aUser)
  {
    int index = users.indexOf(aUser);
    return index;
  }
  /* Code from template association_GetMany */
  public Client getClient(int index)
  {
    Client aClient = clients.get(index);
    return aClient;
  }

  public List<Client> getClients()
  {
    List<Client> newClients = Collections.unmodifiableList(clients);
    return newClients;
  }

  public int numberOfClients()
  {
    int number = clients.size();
    return number;
  }

  public boolean hasClients()
  {
    boolean has = clients.size() > 0;
    return has;
  }

  public int indexOfClient(Client aClient)
  {
    int index = clients.indexOf(aClient);
    return index;
  }
  /* Code from template association_GetMany */
  public Vendor getVendor(int index)
  {
    Vendor aVendor = vendors.get(index);
    return aVendor;
  }

  public List<Vendor> getVendors()
  {
    List<Vendor> newVendors = Collections.unmodifiableList(vendors);
    return newVendors;
  }

  public int numberOfVendors()
  {
    int number = vendors.size();
    return number;
  }

  public boolean hasVendors()
  {
    boolean has = vendors.size() > 0;
    return has;
  }

  public int indexOfVendor(Vendor aVendor)
  {
    int index = vendors.indexOf(aVendor);
    return index;
  }
  /* Code from template association_GetMany */
  public Property getProperty(int index)
  {
    Property aProperty = properties.get(index);
    return aProperty;
  }

  public List<Property> getProperties()
  {
    List<Property> newProperties = Collections.unmodifiableList(properties);
    return newProperties;
  }

  public int numberOfProperties()
  {
    int number = properties.size();
    return number;
  }

  public boolean hasProperties()
  {
    boolean has = properties.size() > 0;
    return has;
  }

  public int indexOfProperty(Property aProperty)
  {
    int index = properties.indexOf(aProperty);
    return index;
  }
  /* Code from template association_MinimumNumberOfMethod */
  public static int minimumNumberOfUsers()
  {
    return 0;
  }
  /* Code from template association_AddManyToOne */
  public User addUser(UUID aCanonicalId, DateTime aCreatedAt, DateTime aUpdatedAt, String aEmail, String aDisplayName)
  {
    return new User(aCanonicalId, aCreatedAt, aUpdatedAt, aEmail, aDisplayName, this);
  }

  public boolean addUser(User aUser)
  {
    boolean wasAdded = false;
    if (users.contains(aUser)) { return false; }
    Organization existingOrganization = aUser.getOrganization();
    boolean isNewOrganization = existingOrganization != null && !this.equals(existingOrganization);
    if (isNewOrganization)
    {
      aUser.setOrganization(this);
    }
    else
    {
      users.add(aUser);
    }
    wasAdded = true;
    return wasAdded;
  }

  public boolean removeUser(User aUser)
  {
    boolean wasRemoved = false;
    //Unable to remove aUser, as it must always have a organization
    if (!this.equals(aUser.getOrganization()))
    {
      users.remove(aUser);
      wasRemoved = true;
    }
    return wasRemoved;
  }
  /* Code from template association_AddIndexControlFunctions */
  public boolean addUserAt(User aUser, int index)
  {  
    boolean wasAdded = false;
    if(addUser(aUser))
    {
      if(index < 0 ) { index = 0; }
      if(index > numberOfUsers()) { index = numberOfUsers() - 1; }
      users.remove(aUser);
      users.add(index, aUser);
      wasAdded = true;
    }
    return wasAdded;
  }

  public boolean addOrMoveUserAt(User aUser, int index)
  {
    boolean wasAdded = false;
    if(users.contains(aUser))
    {
      if(index < 0 ) { index = 0; }
      if(index > numberOfUsers()) { index = numberOfUsers() - 1; }
      users.remove(aUser);
      users.add(index, aUser);
      wasAdded = true;
    } 
    else 
    {
      wasAdded = addUserAt(aUser, index);
    }
    return wasAdded;
  }
  /* Code from template association_MinimumNumberOfMethod */
  public static int minimumNumberOfClients()
  {
    return 0;
  }
  /* Code from template association_AddManyToOne */
  public Client addClient(UUID aCanonicalId, DateTime aCreatedAt, DateTime aUpdatedAt, String aName)
  {
    return new Client(aCanonicalId, aCreatedAt, aUpdatedAt, aName, this);
  }

  public boolean addClient(Client aClient)
  {
    boolean wasAdded = false;
    if (clients.contains(aClient)) { return false; }
    Organization existingOrganization = aClient.getOrganization();
    boolean isNewOrganization = existingOrganization != null && !this.equals(existingOrganization);
    if (isNewOrganization)
    {
      aClient.setOrganization(this);
    }
    else
    {
      clients.add(aClient);
    }
    wasAdded = true;
    return wasAdded;
  }

  public boolean removeClient(Client aClient)
  {
    boolean wasRemoved = false;
    //Unable to remove aClient, as it must always have a organization
    if (!this.equals(aClient.getOrganization()))
    {
      clients.remove(aClient);
      wasRemoved = true;
    }
    return wasRemoved;
  }
  /* Code from template association_AddIndexControlFunctions */
  public boolean addClientAt(Client aClient, int index)
  {  
    boolean wasAdded = false;
    if(addClient(aClient))
    {
      if(index < 0 ) { index = 0; }
      if(index > numberOfClients()) { index = numberOfClients() - 1; }
      clients.remove(aClient);
      clients.add(index, aClient);
      wasAdded = true;
    }
    return wasAdded;
  }

  public boolean addOrMoveClientAt(Client aClient, int index)
  {
    boolean wasAdded = false;
    if(clients.contains(aClient))
    {
      if(index < 0 ) { index = 0; }
      if(index > numberOfClients()) { index = numberOfClients() - 1; }
      clients.remove(aClient);
      clients.add(index, aClient);
      wasAdded = true;
    } 
    else 
    {
      wasAdded = addClientAt(aClient, index);
    }
    return wasAdded;
  }
  /* Code from template association_MinimumNumberOfMethod */
  public static int minimumNumberOfVendors()
  {
    return 0;
  }
  /* Code from template association_AddManyToOne */
  public Vendor addVendor(UUID aCanonicalId, DateTime aCreatedAt, DateTime aUpdatedAt, String aName)
  {
    return new Vendor(aCanonicalId, aCreatedAt, aUpdatedAt, aName, this);
  }

  public boolean addVendor(Vendor aVendor)
  {
    boolean wasAdded = false;
    if (vendors.contains(aVendor)) { return false; }
    Organization existingOrganization = aVendor.getOrganization();
    boolean isNewOrganization = existingOrganization != null && !this.equals(existingOrganization);
    if (isNewOrganization)
    {
      aVendor.setOrganization(this);
    }
    else
    {
      vendors.add(aVendor);
    }
    wasAdded = true;
    return wasAdded;
  }

  public boolean removeVendor(Vendor aVendor)
  {
    boolean wasRemoved = false;
    //Unable to remove aVendor, as it must always have a organization
    if (!this.equals(aVendor.getOrganization()))
    {
      vendors.remove(aVendor);
      wasRemoved = true;
    }
    return wasRemoved;
  }
  /* Code from template association_AddIndexControlFunctions */
  public boolean addVendorAt(Vendor aVendor, int index)
  {  
    boolean wasAdded = false;
    if(addVendor(aVendor))
    {
      if(index < 0 ) { index = 0; }
      if(index > numberOfVendors()) { index = numberOfVendors() - 1; }
      vendors.remove(aVendor);
      vendors.add(index, aVendor);
      wasAdded = true;
    }
    return wasAdded;
  }

  public boolean addOrMoveVendorAt(Vendor aVendor, int index)
  {
    boolean wasAdded = false;
    if(vendors.contains(aVendor))
    {
      if(index < 0 ) { index = 0; }
      if(index > numberOfVendors()) { index = numberOfVendors() - 1; }
      vendors.remove(aVendor);
      vendors.add(index, aVendor);
      wasAdded = true;
    } 
    else 
    {
      wasAdded = addVendorAt(aVendor, index);
    }
    return wasAdded;
  }
  /* Code from template association_MinimumNumberOfMethod */
  public static int minimumNumberOfProperties()
  {
    return 0;
  }
  /* Code from template association_AddManyToOne */
  public Property addProperty(UUID aCanonicalId, DateTime aCreatedAt, DateTime aUpdatedAt, String aAddress)
  {
    return new Property(aCanonicalId, aCreatedAt, aUpdatedAt, aAddress, this);
  }

  public boolean addProperty(Property aProperty)
  {
    boolean wasAdded = false;
    if (properties.contains(aProperty)) { return false; }
    Organization existingOrganization = aProperty.getOrganization();
    boolean isNewOrganization = existingOrganization != null && !this.equals(existingOrganization);
    if (isNewOrganization)
    {
      aProperty.setOrganization(this);
    }
    else
    {
      properties.add(aProperty);
    }
    wasAdded = true;
    return wasAdded;
  }

  public boolean removeProperty(Property aProperty)
  {
    boolean wasRemoved = false;
    //Unable to remove aProperty, as it must always have a organization
    if (!this.equals(aProperty.getOrganization()))
    {
      properties.remove(aProperty);
      wasRemoved = true;
    }
    return wasRemoved;
  }
  /* Code from template association_AddIndexControlFunctions */
  public boolean addPropertyAt(Property aProperty, int index)
  {  
    boolean wasAdded = false;
    if(addProperty(aProperty))
    {
      if(index < 0 ) { index = 0; }
      if(index > numberOfProperties()) { index = numberOfProperties() - 1; }
      properties.remove(aProperty);
      properties.add(index, aProperty);
      wasAdded = true;
    }
    return wasAdded;
  }

  public boolean addOrMovePropertyAt(Property aProperty, int index)
  {
    boolean wasAdded = false;
    if(properties.contains(aProperty))
    {
      if(index < 0 ) { index = 0; }
      if(index > numberOfProperties()) { index = numberOfProperties() - 1; }
      properties.remove(aProperty);
      properties.add(index, aProperty);
      wasAdded = true;
    } 
    else 
    {
      wasAdded = addPropertyAt(aProperty, index);
    }
    return wasAdded;
  }

  public void delete()
  {
    while (users.size() > 0)
    {
      User aUser = users.get(users.size() - 1);
      aUser.delete();
      users.remove(aUser);
    }
    
    while (clients.size() > 0)
    {
      Client aClient = clients.get(clients.size() - 1);
      aClient.delete();
      clients.remove(aClient);
    }
    
    while (vendors.size() > 0)
    {
      Vendor aVendor = vendors.get(vendors.size() - 1);
      aVendor.delete();
      vendors.remove(aVendor);
    }
    
    while (properties.size() > 0)
    {
      Property aProperty = properties.get(properties.size() - 1);
      aProperty.delete();
      properties.remove(aProperty);
    }
    
    super.delete();
  }


  public String toString()
  {
    return super.toString() + "["+
            "name" + ":" + getName()+ "," +
            "legalName" + ":" + getLegalName()+ "," +
            "defaultCurrency" + ":" + getDefaultCurrency()+ "]";
  }
}