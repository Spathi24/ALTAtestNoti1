/*PLEASE DO NOT EDIT THIS CODE*/
/*This code was generated using the UMPLE 1.37.0.8623.1cd95c4b0 modeling language!*/

package project_db.v01;
import java.util.*;

// line 169 "../../model-v0.1.ump"
public class Vendor extends CanonicalEntity
{

  //------------------------
  // MEMBER VARIABLES
  //------------------------

  //Vendor Attributes
  private String name;
  private String email;
  private String phone;
  private String taxId;
  private String paymentTerms;

  //Vendor Associations
  private Organization organization;

  //------------------------
  // CONSTRUCTOR
  //------------------------

  public Vendor(UUID aCanonicalId, DateTime aCreatedAt, DateTime aUpdatedAt, String aName, Organization aOrganization)
  {
    super(aCanonicalId, aCreatedAt, aUpdatedAt);
    name = aName;
    email = null;
    phone = null;
    taxId = null;
    paymentTerms = null;
    boolean didAddOrganization = setOrganization(aOrganization);
    if (!didAddOrganization)
    {
      throw new RuntimeException("Unable to create vendor due to organization. See https://manual.umple.org?RE002ViolationofAssociationMultiplicity.html");
    }
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

  public boolean setEmail(String aEmail)
  {
    boolean wasSet = false;
    email = aEmail;
    wasSet = true;
    return wasSet;
  }

  public boolean setPhone(String aPhone)
  {
    boolean wasSet = false;
    phone = aPhone;
    wasSet = true;
    return wasSet;
  }

  public boolean setTaxId(String aTaxId)
  {
    boolean wasSet = false;
    taxId = aTaxId;
    wasSet = true;
    return wasSet;
  }

  public boolean setPaymentTerms(String aPaymentTerms)
  {
    boolean wasSet = false;
    paymentTerms = aPaymentTerms;
    wasSet = true;
    return wasSet;
  }

  public String getName()
  {
    return name;
  }

  public String getEmail()
  {
    return email;
  }

  public String getPhone()
  {
    return phone;
  }

  public String getTaxId()
  {
    return taxId;
  }

  public String getPaymentTerms()
  {
    return paymentTerms;
  }
  /* Code from template association_GetOne */
  public Organization getOrganization()
  {
    return organization;
  }
  /* Code from template association_SetOneToMany */
  public boolean setOrganization(Organization aOrganization)
  {
    boolean wasSet = false;
    if (aOrganization == null)
    {
      return wasSet;
    }

    Organization existingOrganization = organization;
    organization = aOrganization;
    if (existingOrganization != null && !existingOrganization.equals(aOrganization))
    {
      existingOrganization.removeVendor(this);
    }
    organization.addVendor(this);
    wasSet = true;
    return wasSet;
  }

  public void delete()
  {
    Organization placeholderOrganization = organization;
    this.organization = null;
    if(placeholderOrganization != null)
    {
      placeholderOrganization.removeVendor(this);
    }
    super.delete();
  }


  public String toString()
  {
    return super.toString() + "["+
            "name" + ":" + getName()+ "," +
            "email" + ":" + getEmail()+ "," +
            "phone" + ":" + getPhone()+ "," +
            "taxId" + ":" + getTaxId()+ "," +
            "paymentTerms" + ":" + getPaymentTerms()+ "]" + System.getProperties().getProperty("line.separator") +
            "  " + "organization = "+(getOrganization()!=null?Integer.toHexString(System.identityHashCode(getOrganization())):"null");
  }
}